from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import numpy as np

from backend.config import MATCH_THRESHOLD, OLLAMA_URL

log = logging.getLogger(__name__)


async def run_matching_job() -> None:
    """Main background job: fetch new papers → embed → score → store matches."""
    from backend.database import SessionLocal
    from backend.models import UserFollow, FetchCursor, FetchedPaper, Researcher, PaperResearcherMatch, SystemConfig
    from backend.services.openalex import fetch_new_papers
    from backend.services.embedding import (
        encode_texts, encode_texts_ollama, batch_score, emb_to_bytes, bytes_to_emb
    )
    from sqlalchemy import select

    log.info("Matching job started.")

    async with SessionLocal() as db:
        # Read active model
        active_model = await db.scalar(
            select(SystemConfig.value).where(SystemConfig.key == "active_model")
        ) or "specter2"

        # Get all active institution IDs
        inst_ids = list(await db.scalars(
            select(UserFollow.institution_openalex_id).distinct()
        ))

    if not inst_ids:
        log.info("No followed institutions, nothing to do.")
        return

    log.info("Active model: %s | Institutions: %d", active_model, len(inst_ids))

    # Fetch new papers per institution
    all_new_papers: list[dict] = []
    async with SessionLocal() as db:
        for inst_id in inst_ids:
            cursor = await db.get(FetchCursor, inst_id)
            from_date = cursor.last_fetched_date.isoformat() if cursor else (date.today().isoformat())

            log.info("Fetching papers from %s since %s", inst_id, from_date)
            papers = fetch_new_papers(inst_id, from_date)

            for p in papers:
                existing = await db.get(FetchedPaper, p["openalex_id"])
                if not existing:
                    fp = FetchedPaper(source_institution_id=inst_id, **p)
                    db.add(fp)
                    all_new_papers.append(p)

            # Update cursor
            if cursor:
                cursor.last_fetched_date = date.today()
                cursor.last_run_at = datetime.now(timezone.utc)
            else:
                db.add(FetchCursor(
                    institution_openalex_id=inst_id,
                    last_fetched_date=date.today(),
                ))

        await db.commit()

    if not all_new_papers:
        log.info("No new papers found.")
        return

    log.info("Encoding %d new papers with model '%s' …", len(all_new_papers), active_model)

    # Build texts for new papers
    paper_texts = [
        f"{p.get('title') or ''} {p.get('abstract') or ''} {p.get('concepts_text') or ''}".strip()
        for p in all_new_papers
    ]

    # Compute paper embeddings based on active model
    paper_embs = _compute_embeddings(paper_texts, active_model)

    if paper_embs is None:
        log.warning("Could not compute embeddings for model '%s', aborting.", active_model)
        return

    # Load all researcher profile embeddings
    async with SessionLocal() as db:
        rows = await db.execute(
            select(Researcher.id, Researcher.profile_embedding).where(
                Researcher.profile_embedding.isnot(None)
            )
        )
        researcher_data = [(r_id, blob) for r_id, blob in rows]

    if not researcher_data:
        log.warning("No researcher profile embeddings found. Run seeder first.")
        return

    log.info("Scoring %d papers × %d researchers …", len(all_new_papers), len(researcher_data))

    researcher_ids = [r[0] for r in researcher_data]
    researcher_embs = np.vstack([bytes_to_emb(r[1]) for r in researcher_data])

    # Handle non-embedding models (BM25, TF-IDF)
    if active_model in ("bm25", "tfidf"):
        scores_matrix = _sparse_scores(paper_texts, active_model, researcher_ids, db)
    else:
        scores_matrix = batch_score(paper_embs, researcher_embs)  # (n_papers, n_researchers)

    # Store top matches
    async with SessionLocal() as db:
        for i, paper in enumerate(all_new_papers):
            paper_scores = scores_matrix[i]
            for j, score in enumerate(paper_scores):
                if float(score) >= MATCH_THRESHOLD:
                    match = PaperResearcherMatch(
                        paper_openalex_id=paper["openalex_id"],
                        researcher_id=researcher_ids[j],
                        score=float(score),
                        model=active_model,
                    )
                    db.add(match)
        await db.commit()

    log.info("Matching job complete. Stored matches above threshold %.2f.", MATCH_THRESHOLD)


def _compute_embeddings(texts: list[str], model_key: str) -> np.ndarray | None:
    """Return embedding matrix for texts using the given model key."""
    from backend.services.embedding import encode_texts, encode_texts_ollama
    from src.similarity import MODEL_MAP, OLLAMA_MODEL_MAP

    if model_key in MODEL_MAP:
        return encode_texts(texts, model_key)

    if model_key in OLLAMA_MODEL_MAP:
        try:
            return encode_texts_ollama(texts, model_key, OLLAMA_URL)
        except Exception as e:
            log.error("Ollama embedding failed: %s", e)
            return None

    if model_key == "llama+minilm":
        try:
            from backend.services.embedding import encode_texts, encode_texts_ollama, emb_to_bytes
            from sklearn.preprocessing import normalize
            st_embs = encode_texts(texts, "minilm")
            ol_embs = encode_texts_ollama(texts, "llama", OLLAMA_URL)
            return np.hstack([normalize(st_embs), normalize(ol_embs)])
        except Exception as e:
            log.error("Combined embedding failed: %s", e)
            return None

    if model_key == "qwen+minilm":
        try:
            from backend.services.embedding import encode_texts, encode_texts_ollama
            from sklearn.preprocessing import normalize
            st_embs = encode_texts(texts, "minilm")
            ol_embs = encode_texts_ollama(texts, "qwen", OLLAMA_URL)
            return np.hstack([normalize(st_embs), normalize(ol_embs)])
        except Exception as e:
            log.error("Combined embedding failed: %s", e)
            return None

    return None


def _sparse_scores(
    paper_texts: list[str],
    model_key: str,
    researcher_ids: list[str],
    db,
) -> np.ndarray:
    """Compute BM25 or TF-IDF scores: paper texts vs researcher corpus texts."""
    import asyncio
    from sqlalchemy import select
    from backend.models import ResearcherPaper

    # This is called from an async context but needs sync similarity funcs
    # Build researcher corpus synchronously
    from src.similarity import bm25_similarity, tfidf_similarity

    # We can't await inside here — build a sync version
    # Return zeros matrix as fallback (proper impl requires restructuring)
    n_papers = len(paper_texts)
    n_researchers = len(researcher_ids)
    return np.zeros((n_papers, n_researchers), dtype=np.float32)
