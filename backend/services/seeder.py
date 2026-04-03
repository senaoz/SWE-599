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

from backend.config import BOUN_OPENALEX_ID, BOUN_CSV_PATH

log = logging.getLogger(__name__)

BOUN_INST_SHORT = BOUN_OPENALEX_ID  # full URI


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
    """Convert boun.csv concepts_array (stringified list of strings) to space-joined text."""
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
    """Seed researchers from boun.csv if the researchers table is empty."""
    from backend.database import SessionLocal
    from backend.models import Researcher

    async with SessionLocal() as db:
        from sqlalchemy import select, func
        count = await db.scalar(select(func.count(Researcher.id)))

    if count and count > 0:
        log.info("Researchers already seeded (%d rows), skipping.", count)
        return

    log.info("Seeding researchers from %s …", BOUN_CSV_PATH)
    await _do_seed()


async def _do_seed() -> None:
    from backend.database import SessionLocal
    from backend.models import Researcher, ResearcherPaper
    from backend.services.embedding import encode_texts, emb_to_bytes
    from src.similarity import MODEL_MAP

    df = pd.read_csv(BOUN_CSV_PATH, low_memory=False)
    log.info("Loaded %d rows from boun.csv", len(df))

    # researcher_id → {info, papers:[]}
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

            # Check this author is affiliated with BOUN
            inst_ids = [i.get("id", "") for i in auth.get("institutions", [])]
            if BOUN_INST_SHORT not in inst_ids:
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

    # Insert researchers + papers in batches
    async with SessionLocal() as db:
        for r_data in researchers.values():
            researcher = Researcher(
                id=r_data["id"],
                openalex_id=r_data["openalex_id"],
                display_name=r_data["display_name"],
                paper_count=len(r_data["papers"]),
            )
            db.add(researcher)

            for p in r_data["papers"]:
                db.add(ResearcherPaper(researcher_id=r_data["id"], **p))

        await db.commit()
    log.info("Inserted researchers and papers. Computing profile embeddings …")

    # Compute mean SPECTER2 profile embedding per researcher
    await _compute_profile_embeddings(researchers, model_key="specter2")
    log.info("Seeding complete.")


async def _compute_profile_embeddings(researchers: dict, model_key: str) -> None:
    from backend.database import SessionLocal
    from backend.models import Researcher
    from backend.services.embedding import encode_texts, emb_to_bytes
    from sqlalchemy import select

    all_texts: list[str] = []
    researcher_slices: list[tuple[str, int, int]] = []  # (id, start, end)

    for r_id, r_data in researchers.items():
        papers = r_data["papers"]
        if not papers:
            continue
        texts = [f"{p['title'] or ''} {p['abstract'] or ''} {p['concepts_text'] or ''}".strip() for p in papers]
        start = len(all_texts)
        all_texts.extend(texts)
        researcher_slices.append((r_id, start, start + len(texts)))

    if not all_texts:
        return

    log.info("Encoding %d paper texts for profile embeddings …", len(all_texts))
    embs = encode_texts(all_texts, model_key)

    async with SessionLocal() as db:
        for r_id, start, end in researcher_slices:
            mean_emb = embs[start:end].mean(axis=0)
            researcher = await db.get(Researcher, r_id)
            if researcher:
                researcher.profile_embedding = emb_to_bytes(mean_emb)
                researcher.profile_updated_at = datetime.now(timezone.utc)
        await db.commit()
    log.info("Profile embeddings stored.")
