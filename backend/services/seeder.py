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
        paper_emb_count = await db.scalar(
            select(func.count(ResearcherPaper.id)).where(
                ResearcherPaper.embedding.isnot(None)
            )
        )

    if researcher_count and researcher_count > 0:
        log.info("Researchers already seeded (%d rows).", researcher_count)
        if not paper_emb_count:
            log.info("Paper embeddings missing — starting background computation …")
            asyncio.create_task(_compute_missing_paper_embeddings())
        else:
            log.info("Paper embeddings present (%d rows), skipping.", paper_emb_count)
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

    log.info("Encoding %d paper texts with Qwen (Ollama) …", len(all_texts))
    try:
        import asyncio
        embs = await asyncio.to_thread(encode_texts_ollama, all_texts, RETRIEVE_MODEL, OLLAMA_URL)
    except Exception as e:
        log.error("Qwen embedding failed: %s — skipping embedding step.", e)
        return

    async with SessionLocal() as db:
        # Store mean profile embedding per researcher
        for r_id, start, end in researcher_slices:
            mean_emb = embs[start:end].mean(axis=0)
            researcher = await db.get(Researcher, r_id)
            if researcher:
                researcher.profile_embedding = emb_to_bytes(mean_emb)
                researcher.profile_updated_at = datetime.now(timezone.utc)

        # Batch-load all researcher papers, then update individual embeddings
        all_r_ids = [r_id for r_id, _, _ in researcher_slices]
        result = await db.scalars(
            select(ResearcherPaper).where(ResearcherPaper.researcher_id.in_(all_r_ids))
        )
        paper_map: dict[tuple[str, str], ResearcherPaper] = {
            (p.researcher_id, p.paper_openalex_id): p for p in result
        }

        for idx, (r_id, paper_id) in enumerate(paper_tracking):
            paper = paper_map.get((r_id, paper_id))
            if paper:
                paper.embedding = emb_to_bytes(embs[idx])

        await db.commit()

    log.info("Profile embeddings and individual paper embeddings stored.")


async def _compute_missing_paper_embeddings() -> None:
    """Compute per-paper Qwen embeddings for already-seeded researchers (upgrade path)."""
    import asyncio
    from backend.database import SessionLocal
    from backend.models import ResearcherPaper, Researcher
    from backend.services.embedding import encode_texts_ollama, emb_to_bytes
    from sqlalchemy import select

    async with SessionLocal() as db:
        papers = list(await db.scalars(select(ResearcherPaper)))

    log.info("Computing Qwen embeddings for %d researcher papers …", len(papers))

    CHUNK = 500
    r_paper_embs: dict[str, list[np.ndarray]] = {}

    for chunk_start in range(0, len(papers), CHUNK):
        chunk = papers[chunk_start:chunk_start + CHUNK]
        texts = [
            f"{p.title or ''} {p.abstract or ''} {p.concepts_text or ''}".strip()
            for p in chunk
        ]

        try:
            embs = await asyncio.to_thread(encode_texts_ollama, texts, RETRIEVE_MODEL, OLLAMA_URL)
        except Exception as e:
            log.error("Qwen embedding failed at chunk %d: %s — aborting.", chunk_start, e)
            return

        async with SessionLocal() as db:
            for paper, emb in zip(chunk, embs):
                p_obj = await db.get(ResearcherPaper, paper.id)
                if p_obj:
                    p_obj.embedding = emb_to_bytes(emb)
            await db.commit()

        for paper, emb in zip(chunk, embs):
            r_paper_embs.setdefault(paper.researcher_id, []).append(emb)

        done = min(chunk_start + CHUNK, len(papers))
        log.info("Paper embeddings: %d/%d committed.", done, len(papers))

    # Update researcher mean profile embeddings
    async with SessionLocal() as db:
        for r_id, emb_list in r_paper_embs.items():
            researcher = await db.get(Researcher, r_id)
            if researcher:
                mean_emb = np.mean(emb_list, axis=0)
                researcher.profile_embedding = emb_to_bytes(mean_emb)
                researcher.profile_updated_at = datetime.now(timezone.utc)
        await db.commit()

    log.info("Missing paper embeddings computed and stored.")
