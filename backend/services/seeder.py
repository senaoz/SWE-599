from __future__ import annotations

import ast
import os
import sys
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.config import BOUN_OPENALEX_ID, BOUN_CSV_PATH, OLLAMA_URL, RETRIEVE_MODEL

log = logging.getLogger(__name__)


def _parse_authorships(val) -> list[dict]:
    if isinstance(val, list):
        return val
    try:
        return ast.literal_eval(val)
    except Exception:
        return []


def _short_id(full_uri: str) -> str:
    """'https://openalex.org/A123' → 'A123'"""
    return full_uri.rsplit("/", 1)[-1]


def _concepts_text(val) -> str:
    if isinstance(val, list):
        names = val
    else:
        try:
            names = ast.literal_eval(val)
        except Exception:
            return ""
    if not isinstance(names, list):
        return ""
    return " ".join(str(n) for n in names if n)


async def seed_if_empty() -> None:
    """Seed researchers from boun.csv if empty. Embedding computation runs in background."""
    import asyncio
    from backend.database import SessionLocal
    from backend.models import Researcher, ResearcherPaper
    from sqlalchemy import select, func

    async with SessionLocal() as db:
        researcher_count = await db.scalar(select(func.count(Researcher.id)))
        total_papers = await db.scalar(select(func.count(ResearcherPaper.id)))
        paper_emb_count = await db.scalar(
            select(func.count(ResearcherPaper.id)).where(
                ResearcherPaper.embedding.isnot(None)
            )
        )

    if researcher_count and researcher_count > 0:
        log.info("Researchers already seeded (%d rows).", researcher_count)
        if paper_emb_count and paper_emb_count >= (total_papers or 0):
            log.info("Paper embeddings present (%d rows), skipping.", paper_emb_count)
        else:
            log.info("Paper embeddings incomplete (%d/%d) — resuming computation …", paper_emb_count or 0, total_papers or 0)
            asyncio.create_task(_compute_missing_paper_embeddings())
        return

    log.info("Seeding researchers from %s …", BOUN_CSV_PATH)
    await _do_seed()


async def _do_seed() -> None:
    from backend.database import SessionLocal
    from backend.models import Researcher, ResearcherPaper

    df = pd.read_csv(BOUN_CSV_PATH, low_memory=False)
    log.info("Loaded %d rows from boun.csv", len(df))

    researchers: dict[str, dict] = {}

    for _, row in df.iterrows():
        authorships = _parse_authorships(row.get("authorships", "[]"))
        abstract = row.get("abstract")
        abstract = str(abstract) if pd.notna(abstract) else ""
        title = row.get("title")
        title = str(title) if pd.notna(title) else ""
        concepts = _concepts_text(row.get("concepts_array", ""))
        pub_year = row.get("publication_year")
        paper_id = str(row.get("id", ""))

        for auth in authorships:
            author = auth.get("author", {})
            author_id = author.get("id", "")
            if not author_id:
                continue
            inst_ids = [i.get("id", "") for i in auth.get("institutions", [])]
            if BOUN_OPENALEX_ID not in inst_ids:
                continue

            short = _short_id(author_id)
            if short not in researchers:
                researchers[short] = {
                    "id": short,
                    "openalex_id": author_id,
                    "display_name": author.get("display_name", "Unknown"),
                    "papers": [],
                }
            researchers[short]["papers"].append({
                "paper_openalex_id": paper_id,
                "title": title,
                "abstract": abstract,
                "concepts_text": concepts,
                "publication_year": int(pub_year) if pd.notna(pub_year) else None,
            })

    log.info("Found %d unique BOUN researchers", len(researchers))

    async with SessionLocal() as db:
        for r_data in researchers.values():
            db.add(Researcher(
                id=r_data["id"],
                openalex_id=r_data["openalex_id"],
                display_name=r_data["display_name"],
                paper_count=len(r_data["papers"]),
            ))
            for p in r_data["papers"]:
                db.add(ResearcherPaper(researcher_id=r_data["id"], **p))
        await db.commit()

    log.info("Inserted researchers and papers. Starting embedding computation in background …")
    import asyncio
    asyncio.create_task(_compute_profile_embeddings(researchers))
    log.info("Seeding complete — embeddings computing in background.")


CACHE_PATH = os.path.join(_ROOT, "research", "data", "embeddings_cache", "boun_qwen_papers.npz")
FETCHED_CACHE_PATH = os.path.join(_ROOT, "research", "data", "embeddings_cache", "fetched_papers_qwen.npz")


async def _compute_profile_embeddings(researchers: dict) -> None:
    """Encode all BOUN papers with Qwen, store individual + mean profile embeddings."""
    from backend.database import SessionLocal
    from backend.models import Researcher, ResearcherPaper
    from backend.services.embedding import encode_texts_ollama, emb_to_bytes
    from sqlalchemy import select, update

    # Build flat list: all paper texts with (researcher_id, paper_openalex_id) tracking
    all_texts: list[str] = []
    paper_tracking: list[tuple[str, str]] = []  # (researcher_id, paper_openalex_id)
    researcher_slices: list[tuple[str, int, int]] = []

    for r_id, r_data in researchers.items():
        papers = r_data["papers"]
        if not papers:
            continue
        texts = [
            f"{p['title'] or ''} {p['abstract'] or ''} {p['concepts_text'] or ''}".strip()
            for p in papers
        ]
        start = len(all_texts)
        all_texts.extend(texts)
        for p in papers:
            paper_tracking.append((r_id, p["paper_openalex_id"]))
        researcher_slices.append((r_id, start, start + len(texts)))

    if not all_texts:
        return

    # Load from cache if available
    if os.path.exists(CACHE_PATH):
        log.info("Loading paper embeddings from cache: %s", CACHE_PATH)
        cache = np.load(CACHE_PATH, allow_pickle=True)
        embs = cache["embeddings"]
        cached_tracking = list(zip(cache["researcher_ids"].tolist(), cache["paper_ids"].tolist()))
        if len(embs) == len(all_texts) and cached_tracking == paper_tracking:
            log.info("Cache hit — %d embeddings loaded.", len(embs))
        else:
            log.warning("Cache mismatch (size or order changed) — recomputing.")
            os.remove(CACHE_PATH)
            embs = None
    else:
        embs = None

    PARTIAL_PATH = CACHE_PATH + ".partial.npz"

    if embs is None:
        # Check for partial progress from a previous interrupted run
        resume_from = 0
        partial_embs: list = []
        if os.path.exists(PARTIAL_PATH):
            try:
                partial = np.load(PARTIAL_PATH, allow_pickle=True)
                partial_embs = [partial["embeddings"]]
                resume_from = int(partial["done"])
                log.info("Resuming from chunk %d/%d (partial cache found).", resume_from, len(all_texts))
            except Exception:
                log.warning("Partial cache corrupt — starting from scratch.")

        CHUNK = 200
        import asyncio
        for chunk_start in range(resume_from, len(all_texts), CHUNK):
            chunk = all_texts[chunk_start:chunk_start + CHUNK]
            try:
                chunk_embs = await asyncio.to_thread(encode_texts_ollama, chunk, RETRIEVE_MODEL, OLLAMA_URL)
                partial_embs.append(chunk_embs)
            except Exception as e:
                log.error("Qwen embedding failed at chunk %d: %s — saving partial progress.", chunk_start, e)
                os.makedirs(os.path.dirname(PARTIAL_PATH), exist_ok=True)
                np.savez_compressed(
                    PARTIAL_PATH,
                    embeddings=np.vstack(partial_embs) if partial_embs else np.array([]),
                    done=chunk_start,
                )
                return
            done = min(chunk_start + CHUNK, len(all_texts))
            log.info("Paper embeddings: %d/%d encoded.", done, len(all_texts))
            # Save partial progress after each chunk
            os.makedirs(os.path.dirname(PARTIAL_PATH), exist_ok=True)
            np.savez_compressed(
                PARTIAL_PATH,
                embeddings=np.vstack(partial_embs),
                done=done,
            )

        embs = np.vstack(partial_embs)

        # Save final cache and remove partial
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        np.savez_compressed(
            CACHE_PATH,
            embeddings=embs,
            researcher_ids=np.array([t[0] for t in paper_tracking]),
            paper_ids=np.array([t[1] for t in paper_tracking]),
        )
        if os.path.exists(PARTIAL_PATH):
            os.remove(PARTIAL_PATH)
        log.info("Paper embeddings cached to %s", CACHE_PATH)

    from sqlalchemy import text as sa_text

    COMMIT_EVERY = 50  # researchers per commit
    for batch_start in range(0, len(researcher_slices), COMMIT_EVERY):
        batch = researcher_slices[batch_start:batch_start + COMMIT_EVERY]
        async with SessionLocal() as db:
            for r_id, start, end in batch:
                mean_emb = embs[start:end].mean(axis=0)
                await db.execute(
                    sa_text(
                        "UPDATE researchers SET profile_embedding=:emb, profile_updated_at=:ts "
                        "WHERE id=:id"
                    ),
                    {"emb": emb_to_bytes(mean_emb), "ts": datetime.now(timezone.utc), "id": r_id},
                )
                for idx in range(start, end):
                    _, paper_id = paper_tracking[idx]
                    await db.execute(
                        sa_text(
                            "UPDATE researcher_papers SET embedding=:emb "
                            "WHERE researcher_id=:r_id AND paper_openalex_id=:p_id"
                        ),
                        {"emb": emb_to_bytes(embs[idx]), "r_id": r_id, "p_id": paper_id},
                    )
            await db.commit()
        done = min(batch_start + COMMIT_EVERY, len(researcher_slices))
        log.info("Profile embeddings: %d/%d researchers committed.", done, len(researcher_slices))

    log.info("Profile embeddings and individual paper embeddings stored.")


async def _compute_missing_paper_embeddings() -> None:
    """Compute per-paper Qwen embeddings for already-seeded researchers (resume-safe)."""
    import asyncio
    from backend.database import SessionLocal
    from backend.models import ResearcherPaper
    from backend.services.embedding import encode_texts_ollama, emb_to_bytes
    from sqlalchemy import select, text as sa_text

    async with SessionLocal() as db:
        rows = list(await db.execute(
            select(ResearcherPaper.id, ResearcherPaper.researcher_id,
                   ResearcherPaper.paper_openalex_id, ResearcherPaper.title,
                   ResearcherPaper.abstract, ResearcherPaper.concepts_text)
            .where(ResearcherPaper.embedding.is_(None))
            .order_by(ResearcherPaper.researcher_id, ResearcherPaper.paper_openalex_id)
        ))

    if not rows:
        log.info("All paper embeddings already present — skipping.")
        return

    texts = [f"{r.title or ''} {r.abstract or ''} {r.concepts_text or ''}".strip() for r in rows]
    log.info("Computing Qwen embeddings for %d remaining papers …", len(texts))

    CHUNK = 200
    for chunk_start in range(0, len(texts), CHUNK):
        chunk_texts = texts[chunk_start:chunk_start + CHUNK]
        chunk_rows = rows[chunk_start:chunk_start + CHUNK]
        try:
            chunk_embs = await asyncio.to_thread(encode_texts_ollama, chunk_texts, RETRIEVE_MODEL, OLLAMA_URL)
        except Exception as e:
            log.error("Qwen embedding failed at chunk %d: %s — will resume on next restart.", chunk_start, e)
            return

        async with SessionLocal() as db:
            for row, emb in zip(chunk_rows, chunk_embs):
                await db.execute(
                    sa_text("UPDATE researcher_papers SET embedding=:emb WHERE id=:id"),
                    {"emb": emb_to_bytes(emb), "id": row.id},
                )
            await db.commit()
        log.info("Paper embeddings: %d/%d committed.", min(chunk_start + CHUNK, len(texts)), len(texts))

    # Recompute profile embeddings from all papers now in DB
    async with SessionLocal() as db:
        all_rows = list(await db.execute(
            select(ResearcherPaper.researcher_id, ResearcherPaper.embedding)
            .where(ResearcherPaper.embedding.isnot(None))
        ))
    r_embs: dict[str, list[np.ndarray]] = {}
    for row in all_rows:
        r_embs.setdefault(row.researcher_id, []).append(
            np.frombuffer(row.embedding, dtype=np.float32)
        )
    async with SessionLocal() as db:
        for r_id, emb_list in r_embs.items():
            mean_emb = np.mean(emb_list, axis=0)
            await db.execute(
                sa_text("UPDATE researchers SET profile_embedding=:emb, profile_updated_at=:ts WHERE id=:id"),
                {"emb": emb_to_bytes(mean_emb), "ts": datetime.now(timezone.utc), "id": r_id},
            )
        await db.commit()

    log.info("Missing paper embeddings computed and stored.")


async def export_fetched_paper_embeddings() -> None:
    """Dump all fetched_papers embeddings to an .npz cache for offline research use."""
    from backend.database import SessionLocal
    from backend.models import FetchedPaper
    from sqlalchemy import select

    async with SessionLocal() as db:
        rows = list(await db.execute(
            select(
                FetchedPaper.openalex_id,
                FetchedPaper.source_institution_id,
                FetchedPaper.source_institution_name,
                FetchedPaper.embedding,
            ).where(FetchedPaper.embedding.isnot(None))
            .order_by(FetchedPaper.openalex_id)
        ))

    if not rows:
        log.info("No fetched paper embeddings to export.")
        return

    embs = np.vstack([np.frombuffer(row.embedding, dtype=np.float32) for row in rows])
    os.makedirs(os.path.dirname(FETCHED_CACHE_PATH), exist_ok=True)
    np.savez_compressed(
        FETCHED_CACHE_PATH,
        embeddings=embs,
        paper_ids=np.array([row.openalex_id for row in rows]),
        institution_ids=np.array([row.source_institution_id or "" for row in rows]),
        institution_names=np.array([row.source_institution_name or "" for row in rows]),
    )
    log.info("Exported %d fetched paper embeddings → %s", len(rows), FETCHED_CACHE_PATH)
