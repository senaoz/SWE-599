from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from datetime import date

import numpy as np
import pandas as pd

from backend.config import RESEARCH_DIR, EMBEDDING_CACHE_PATH, EMBEDDING_VERSION

_RESEARCH = os.path.abspath(RESEARCH_DIR)
if _RESEARCH not in sys.path:
    sys.path.insert(0, _RESEARCH)

log = logging.getLogger(__name__)

EMBED_CHUNK = 200
INSERT_CHUNK = 1000


def _short_id(full_uri: str) -> str:
    """'https://openalex.org/A123' → 'A123'"""
    return full_uri.rsplit("/", 1)[-1]


def normalize_doi(doi: str | None) -> str | None:
    """'https://doi.org/10.1/AbC' or '10.1/AbC' → '10.1/abc'; None for empty."""
    if not doi:
        return None
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi or None


def load_tables(data_dir: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Rows for researchers, boun_works and boun_authorships from the cleaned BOUN data."""
    works = pd.read_csv(os.path.join(data_dir, "boun_works.csv.gz"), keep_default_na=False)
    people = pd.read_csv(os.path.join(data_dir, "researchers.csv.gz"), keep_default_na=False)
    links = pd.read_csv(os.path.join(data_dir, "researcher_works.csv.gz"), keep_default_na=False)

    researchers = [
        {"id": _short_id(r.researcher_id), "openalex_id": r.researcher_id,
         "display_name": r.display_name or "Unknown", "paper_count": int(r.n_works)}
        for r in people.itertuples()
    ]
    boun_works = [
        {
            "openalex_id": w.id,
            "doi": normalize_doi(w.doi),
            "duplicate_ids": json.loads(w.duplicate_ids or "[]"),
            "title": w.title or None,
            "abstract": w.abstract or None,
            "abstract_source": w.abstract_source,
            "type": w.type or None,
            "first_date": date.fromisoformat(w.first_date) if w.first_date else None,
            "n_authors": len(json.loads(w.author_ids or "[]")),
            "large_collaboration": str(w.large_collaboration) == "True",
            "language_flag": w.language_flag or None,
        }
        for w in works.itertuples()
    ]
    known = {r["openalex_id"] for r in researchers}
    authorships = [
        {"work_id": l.work_id, "researcher_id": _short_id(l.researcher_id)}
        for l in links.itertuples() if l.researcher_id in known
    ]
    return researchers, boun_works, authorships


def cache_key(text: str) -> str:
    """Key of the research embedding cache (src.rankers_v2.EmbeddingCache)."""
    return hashlib.sha256(text.encode()).hexdigest()


def cached_vectors(texts: dict[str, str], cache_path: str) -> dict[str, np.ndarray]:
    """Vectors from the research cache for the texts it holds, by work id."""
    if not os.path.exists(cache_path):
        log.info("No embedding cache at %s — every work is embedded live.", cache_path)
        return {}
    with np.load(cache_path) as cache:
        keys = set(cache.files)
        return {wid: cache[cache_key(t)] for wid, t in texts.items() if cache_key(t) in keys}


async def seed_if_empty() -> None:
    """Load the cleaned BOUN data if the tables are empty, then embed works in the background."""
    import asyncio
    from sqlalchemy import select, func
    from backend.database import SessionLocal
    from backend.models import Researcher

    async with SessionLocal() as db:
        researcher_count = await db.scalar(select(func.count(Researcher.id)))

    if researcher_count:
        log.info("BOUN data already loaded (%d researchers).", researcher_count)
    else:
        await _load_boun_data()
    asyncio.create_task(embed_missing_works())


async def _load_boun_data() -> None:
    from sqlalchemy import insert
    from backend.database import SessionLocal
    from backend.models import Researcher, BounWork, BounAuthorship

    data_dir = os.path.join(RESEARCH_DIR, "data", "boun")
    log.info("Loading cleaned BOUN data from %s …", data_dir)
    researchers, works, authorships = load_tables(data_dir)

    async with SessionLocal() as db:
        for model, rows in ((Researcher, researchers), (BounWork, works), (BounAuthorship, authorships)):
            for start in range(0, len(rows), INSERT_CHUNK):
                await db.execute(insert(model), rows[start:start + INSERT_CHUNK])
        await db.commit()
    log.info("Loaded %d researchers, %d works, %d authorships.", len(researchers), len(works), len(authorships))


async def embed_missing_works() -> None:
    """Embed BOUN works that have no vector at the current EMBEDDING_VERSION, reusing the research
    cache when the text matches. Commits per chunk, so a failed run resumes where it stopped."""
    import asyncio
    from sqlalchemy import select, update, or_
    from backend.database import SessionLocal
    from backend.models import BounWork
    from backend.services.embedding import encode, emb_to_list
    from src.boun_data import work_texts

    async with SessionLocal() as db:
        todo = list(await db.scalars(
            select(BounWork.openalex_id).where(or_(
                BounWork.embedding.is_(None), BounWork.embedding_version != EMBEDDING_VERSION,
            ))
        ))
    if not todo:
        log.info("All BOUN works are embedded at %s.", EMBEDDING_VERSION)
        return

    # Same text as the research vectors; Crossref/S2 abstracts go into the vector only (D5).
    all_texts = work_texts(RESEARCH_DIR)
    texts = {wid: all_texts.get(wid, "") for wid in todo}
    empty = [wid for wid, t in texts.items() if not t]
    texts = {wid: t for wid, t in texts.items() if t}
    if empty:
        log.warning("%d work(s) have no title or abstract — not embedded.", len(empty))

    cached = cached_vectors(texts, EMBEDDING_CACHE_PATH)
    live = [wid for wid in texts if wid not in cached]
    log.info("Embedding %d BOUN works: %d from the cache (%.1f%%), %d live.",
             len(texts), len(cached), 100 * len(cached) / max(len(texts), 1), len(live))

    async def store(vectors: dict[str, np.ndarray]) -> None:
        async with SessionLocal() as db:
            for wid, vec in vectors.items():
                await db.execute(
                    update(BounWork).where(BounWork.openalex_id == wid)
                    .values(embedding=emb_to_list(vec), embedding_version=EMBEDDING_VERSION)
                )
            await db.commit()

    for start in range(0, len(cached), INSERT_CHUNK):
        await store({wid: cached[wid] for wid in list(cached)[start:start + INSERT_CHUNK]})

    for start in range(0, len(live), EMBED_CHUNK):
        chunk = live[start:start + EMBED_CHUNK]
        try:
            embs = await asyncio.to_thread(encode, [texts[wid] for wid in chunk])
        except Exception as e:
            log.error("Embedding failed at %d/%d (%s) — resumes on the next start.", start, len(live), e)
            return
        await store(dict(zip(chunk, embs)))
        log.info("BOUN works embedded live: %d/%d.", min(start + EMBED_CHUNK, len(live)), len(live))

    log.info("BOUN works embedded at %s.", EMBEDDING_VERSION)
