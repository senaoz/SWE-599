from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

import numpy as np

from backend.config import (
    MATCH_THRESHOLD,
    OLLAMA_URL,
    RETRIEVE_MODEL,
    RAG_RETRIEVE_TOP_K,
    RAG_LLM_TOP_K,
    RAG_CONTEXT_PAPERS,
    LLM_GENERATE_MODEL,
)

log = logging.getLogger(__name__)


async def run_matching_job() -> None:
    """2-stage RAG matching: Stage 1 Qwen retrieve → Stage 2 Llama generate."""
    from backend.database import SessionLocal
    from backend.models import (
        UserFollow, FetchCursor, FetchedPaper,
        ResearcherPaper, PaperResearcherMatch,
    )
    from backend.services.openalex import fetch_new_papers
    from backend.services.embedding import encode_texts_ollama, batch_score, emb_to_bytes, bytes_to_emb
    from sqlalchemy import select

    log.info("RAG matching job started.")

    # --- Get followed institutions ---
    async with SessionLocal() as db:
        inst_ids = list(await db.scalars(
            select(UserFollow.institution_openalex_id).distinct()
        ))

    if not inst_ids:
        log.info("No followed institutions, nothing to do.")
        return

    # --- Fetch new papers ---
    all_new_papers: list[dict] = []
    async with SessionLocal() as db:
        for inst_id in inst_ids:
            cursor = await db.get(FetchCursor, inst_id)
            from_date = cursor.last_fetched_date.isoformat() if cursor else date.today().isoformat()

            log.info("Fetching papers from %s since %s", inst_id, from_date)
            papers = fetch_new_papers(inst_id, from_date)

            for p in papers:
                existing = await db.get(FetchedPaper, p["openalex_id"])
                if not existing:
                    db.add(FetchedPaper(source_institution_id=inst_id, **p))
                    all_new_papers.append(p)

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

    # --- STAGE 1: RETRIEVE (Qwen embeddings) ---
    paper_texts = [
        f"{p.get('title') or ''} {p.get('abstract') or ''} {p.get('concepts_text') or ''}".strip()
        for p in all_new_papers
    ]

    log.info("Encoding %d new papers with Qwen …", len(paper_texts))
    try:
        import asyncio
        new_paper_embs = await asyncio.to_thread(
            encode_texts_ollama, paper_texts, RETRIEVE_MODEL, OLLAMA_URL
        )
    except Exception as e:
        log.error("Qwen encoding failed: %s — aborting job.", e)
        return

    # Load all individual BOUN paper embeddings
    async with SessionLocal() as db:
        rows = await db.execute(
            select(
                ResearcherPaper.researcher_id,
                ResearcherPaper.paper_openalex_id,
                ResearcherPaper.title,
                ResearcherPaper.abstract,
                ResearcherPaper.embedding,
            ).where(ResearcherPaper.embedding.isnot(None))
        )
        boun_papers = list(rows)

    if not boun_papers:
        log.warning("No individual BOUN paper embeddings found. Wait for seeder to finish.")
        return

    log.info("Loaded %d BOUN paper embeddings.", len(boun_papers))
    boun_embs = np.vstack([bytes_to_emb(row.embedding) for row in boun_papers])

    # Cosine similarity: (N_new_papers, N_boun_papers)
    scores_matrix = batch_score(new_paper_embs, boun_embs)

    # --- STAGE 2: GENERATE + STORE ---
    async with SessionLocal() as db:
        for i, new_paper in enumerate(all_new_papers):
            paper_scores = scores_matrix[i]

            # Group BOUN papers by researcher, keep only above threshold
            researcher_hits: dict[str, list[tuple[float, object]]] = {}
            for j, boun_row in enumerate(boun_papers):
                score = float(paper_scores[j])
                if score < MATCH_THRESHOLD:
                    continue
                r_id = boun_row.researcher_id
                researcher_hits.setdefault(r_id, []).append((score, boun_row))

            if not researcher_hits:
                continue

            # Sort each researcher's hits by score, get max
            researcher_ranked: dict[str, tuple[float, list]] = {}
            for r_id, hits in researcher_hits.items():
                hits_sorted = sorted(hits, key=lambda x: x[0], reverse=True)
                researcher_ranked[r_id] = (hits_sorted[0][0], hits_sorted)

            # Top-K researchers for LLM rerank
            top_researchers = sorted(
                researcher_ranked.items(),
                key=lambda x: x[1][0],
                reverse=True,
            )[:RAG_RETRIEVE_TOP_K]

            # Stage 2: Llama generate for top LLM_TOP_K
            final_scores: dict[str, tuple[float, list, float | None]] = {}

            for r_id, (emb_score, hits) in top_researchers:
                llm_score: float | None = None
                if len(final_scores) < RAG_LLM_TOP_K:
                    import asyncio
                    llm_score = await asyncio.to_thread(
                        _llm_generate, new_paper, hits[:RAG_CONTEXT_PAPERS]
                    )
                    if llm_score == 0.0:
                        # LLM said IRRELEVANT — skip
                        continue
                    if llm_score is not None:
                        final_score = llm_score
                    else:
                        final_score = emb_score  # Ollama unavailable, fallback
                else:
                    final_score = emb_score  # beyond LLM quota, use Stage 1 score

                if final_score >= MATCH_THRESHOLD:
                    final_scores[r_id] = (final_score, hits, llm_score)

            # Persist matches
            for r_id, (final_score, hits, llm_score) in final_scores.items():
                matched_ids_json = json.dumps([
                    {"id": row.paper_openalex_id, "score": round(float(score), 4)}
                    for score, row in hits[:RAG_CONTEXT_PAPERS]
                ])
                db.add(PaperResearcherMatch(
                    paper_openalex_id=new_paper["openalex_id"],
                    researcher_id=r_id,
                    score=round(final_score, 4),
                    model="qwen+llama",
                    matched_paper_ids=matched_ids_json,
                    llm_score=round(llm_score, 4) if llm_score is not None else None,
                ))

        await db.commit()

    log.info("RAG matching job complete.")


def _llm_generate(new_paper: dict, context_papers: list[tuple[float, object]]) -> float | None:
    """
    Ask Ollama Llama whether the researcher is relevant to a new paper.
    Returns score 0.0-1.0, or None if Ollama is unavailable.
    Returns 0.0 if LLM says IRRELEVANT.
    """
    import requests

    papers_text = "\n".join(
        f"- {row.title or 'Untitled'}: {(row.abstract or '')[:200]}"
        for _, row in context_papers
    )

    prompt = (
        "Decide if a researcher should receive a recommendation for this new paper.\n\n"
        f"NEW PAPER:\n"
        f"Title: {new_paper.get('title', '')}\n"
        f"Abstract: {(new_paper.get('abstract') or '')[:400]}\n\n"
        f"RESEARCHER'S RELATED PAPERS:\n{papers_text}\n\n"
        "Answer with ONLY: RELEVANT <score> or IRRELEVANT <score> (score: 0.0-1.0)\n"
        "Example: RELEVANT 0.85"
    )

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": LLM_GENERATE_MODEL, "prompt": prompt, "stream": False},
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip().upper()

        parts = text.split()
        verdict = parts[0] if parts else ""
        score = 0.5
        if len(parts) > 1:
            try:
                score = max(0.0, min(1.0, float(parts[1])))
            except ValueError:
                pass

        return score if verdict == "RELEVANT" else 0.0

    except Exception as e:
        log.warning("Llama generate step failed (%s) — using Stage 1 score.", e)
        return None
