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

_job_running = False


async def run_matching_job() -> None:
    global _job_running
    if _job_running:
        log.warning("A job is already running — skipping this trigger.")
        return
    _job_running = True
    try:
        await _run_matching_job_impl()
    finally:
        _job_running = False


async def _run_matching_job_impl() -> None:
    from backend.database import SessionLocal
    from backend.models import (
        UserFollow, FetchCursor, FetchedPaper,
        ResearcherPaper, PaperResearcherMatch,
    )
    from backend.services.openalex import fetch_new_papers
    from backend.services.embedding import encode_with_fallback, batch_score, emb_to_list, row_to_emb
    from sqlalchemy import select, func, text as sa_text

    log.info("=" * 60)
    log.info("MATCHING JOB STARTED — %s", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    log.info("=" * 60)

    # --- Get followed institutions ---
    async with SessionLocal() as db:
        rows = await db.execute(
            select(UserFollow.institution_openalex_id, UserFollow.institution_name).distinct()
        )
        institutions = {row.institution_openalex_id: row.institution_name for row in rows}

    if not institutions:
        log.info("No followed institutions — nothing to do.")
        return

    log.info("Following %d institution(s): %s", len(institutions), ", ".join(institutions.values()))

    # --- Fetch new papers ---
    all_new_papers: list[dict] = []
    async with SessionLocal() as db:
        for inst_id, inst_name in institutions.items():
            cursor = await db.get(FetchCursor, inst_id)
            from_date = cursor.last_fetched_date.isoformat() if cursor else date.today().isoformat()

            log.info("[%s] Fetching papers since %s …", inst_name, from_date)
            papers = fetch_new_papers(inst_id, from_date, institution_name=inst_name)
            log.info("[%s] Got %d paper(s) from OpenAlex", inst_name, len(papers))

            # Load existing titles for this institution to catch cross-ID duplicates
            existing_titles: set[str] = set(await db.scalars(
                select(func.lower(FetchedPaper.title))
                .where(FetchedPaper.source_institution_id == inst_id)
                .where(FetchedPaper.title.isnot(None))
            ))

            new_count = 0
            dup_title_count = 0
            seen_this_batch: set[str] = set()

            for p in papers:
                title_key = (p.get("title") or "").lower().strip()

                if title_key:
                    if title_key in existing_titles or title_key in seen_this_batch:
                        log.debug("[%s] Dup title skipped: %.70s", inst_name, title_key)
                        dup_title_count += 1
                        continue
                    seen_this_batch.add(title_key)
                    existing_titles.add(title_key)

                result = await db.execute(
                    sa_text(
                        "INSERT INTO fetched_papers "
                        "(openalex_id, title, abstract, concepts_text, publication_date, "
                        "source_institution_id, source_institution_name) "
                        "VALUES (:oid, :title, :abstract, :concepts, :pub_date, :inst_id, :inst_name) "
                        "ON CONFLICT (openalex_id) DO NOTHING"
                    ),
                    {
                        "oid": p["openalex_id"],
                        "title": p.get("title"),
                        "abstract": p.get("abstract"),
                        "concepts": p.get("concepts_text"),
                        "pub_date": p.get("publication_date"),
                        "inst_id": inst_id,
                        "inst_name": p.get("source_institution_name"),
                    },
                )
                if result.rowcount:
                    all_new_papers.append(p)
                    new_count += 1

            log.info(
                "[%s] %d new | %d id-dupes | %d title-dupes skipped",
                inst_name, new_count, len(papers) - new_count - dup_title_count, dup_title_count,
            )

            if cursor:
                cursor.last_fetched_date = date.today()
                cursor.last_run_at = datetime.now(timezone.utc)
            else:
                db.add(FetchCursor(
                    institution_openalex_id=inst_id,
                    last_fetched_date=date.today(),
                ))
        await db.commit()

    # Pick up any previously-inserted papers that never got encoded (crashed runs)
    async with SessionLocal() as db:
        unembedded = list(await db.execute(
            select(
                FetchedPaper.openalex_id,
                FetchedPaper.title,
                FetchedPaper.abstract,
                FetchedPaper.concepts_text,
            ).where(FetchedPaper.embedding.is_(None))
        ))
    if unembedded:
        log.info("Found %d previously-inserted paper(s) without embeddings — adding to batch.", len(unembedded))
        for row in unembedded:
            if not any(p["openalex_id"] == row.openalex_id for p in all_new_papers):
                all_new_papers.append({
                    "openalex_id": row.openalex_id,
                    "title": row.title,
                    "abstract": row.abstract,
                    "concepts_text": row.concepts_text,
                })

    if not all_new_papers:
        log.info("No new papers to process — job done.")
        return

    log.info("─" * 60)
    log.info("STAGE 1 — Encoding %d new paper(s) with %s …", len(all_new_papers), RETRIEVE_MODEL)

    paper_texts = [
        f"{p.get('title') or ''} {p.get('abstract') or ''} {p.get('concepts_text') or ''}".strip()
        for p in all_new_papers
    ]

    try:
        import asyncio
        new_paper_embs = await asyncio.to_thread(
            encode_with_fallback, paper_texts, RETRIEVE_MODEL, OLLAMA_URL
        )
        log.info("STAGE 1 — Encoded %d papers → shape %s", len(paper_texts), new_paper_embs.shape)
    except Exception as e:
        log.error("STAGE 1 — Encoding failed (%s) — aborting job. Is Ollama running at %s?", e, OLLAMA_URL)
        return

    # Save embeddings back to fetched_papers
    from sqlalchemy import text as sa_text
    async with SessionLocal() as db:
        for paper, emb in zip(all_new_papers, new_paper_embs):
            vec_str = "[" + ",".join(f"{float(x):.8g}" for x in emb) + "]"
            await db.execute(
                sa_text(
                    f"UPDATE fetched_papers SET embedding = '{vec_str}' "
                    f"WHERE openalex_id = :oid"
                ),
                {"oid": paper["openalex_id"]},
            )
        await db.commit()
    log.info("STAGE 1 — Stored %d paper embeddings to DB", len(all_new_papers))

    # Load all BOUN paper embeddings
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
        log.warning("No BOUN paper embeddings found — seeder may still be running. Aborting.")
        return

    log.info("STAGE 1 — Loaded %d BOUN paper embeddings", len(boun_papers))
    boun_embs = np.vstack([row_to_emb(row.embedding) for row in boun_papers])

    # Cosine similarity matrix: (N_new, N_boun)
    scores_matrix = batch_score(new_paper_embs, boun_embs)
    log.info("STAGE 1 — Similarity matrix computed: %s", scores_matrix.shape)

    # --- STAGE 2: GENERATE + STORE ---
    log.info("─" * 60)
    log.info("STAGE 2 — Reranking with %s (top-%d candidates per paper) …", LLM_GENERATE_MODEL, RAG_LLM_TOP_K)

    total_matches = 0
    total_llm_calls = 0
    total_llm_skipped = 0

    async with SessionLocal() as db:
        for i, new_paper in enumerate(all_new_papers):
            paper_title = (new_paper.get("title") or "")[:60]
            paper_scores = scores_matrix[i]

            # Group hits by researcher above threshold
            researcher_hits: dict[str, list[tuple[float, object]]] = {}
            for j, boun_row in enumerate(boun_papers):
                score = float(paper_scores[j])
                if score < MATCH_THRESHOLD:
                    continue
                researcher_hits.setdefault(boun_row.researcher_id, []).append((score, boun_row))

            if not researcher_hits:
                log.debug("[%d/%d] '%s' — no Stage 1 hits above %.2f", i + 1, len(all_new_papers), paper_title, MATCH_THRESHOLD)
                continue

            # Sort each researcher by their best hit score
            researcher_ranked = {
                r_id: (sorted(hits, key=lambda x: x[0], reverse=True))
                for r_id, hits in researcher_hits.items()
            }
            researcher_best = {r_id: hits[0][0] for r_id, hits in researcher_ranked.items()}

            top_researchers = sorted(researcher_best.items(), key=lambda x: x[1], reverse=True)[:RAG_RETRIEVE_TOP_K]

            log.info(
                "[%d/%d] '%s…' — Stage 1: %d researcher(s) above %.2f, top-%d for LLM",
                i + 1, len(all_new_papers), paper_title, len(researcher_hits),
                MATCH_THRESHOLD, min(RAG_LLM_TOP_K, len(top_researchers)),
            )

            final_scores: dict[str, tuple[float, list, float | None]] = {}

            for r_id, emb_score in top_researchers:
                hits = researcher_ranked[r_id]
                llm_score: float | None = None

                if len(final_scores) < RAG_LLM_TOP_K:
                    import asyncio
                    llm_score = await asyncio.to_thread(
                        _llm_generate, new_paper, hits[:RAG_CONTEXT_PAPERS]
                    )
                    total_llm_calls += 1

                    if llm_score == 0.0:
                        log.debug("  [LLM] IRRELEVANT — %s (emb=%.3f)", r_id, emb_score)
                        total_llm_skipped += 1
                        continue

                    if llm_score is not None:
                        final_score = llm_score
                        log.debug("  [LLM] RELEVANT %.3f — %s (emb=%.3f)", llm_score, r_id, emb_score)
                    else:
                        final_score = emb_score
                        log.debug("  [LLM] unavailable — using emb score %.3f for %s", emb_score, r_id)
                else:
                    final_score = emb_score

                if final_score >= MATCH_THRESHOLD:
                    final_scores[r_id] = (final_score, hits, llm_score)

            if not final_scores:
                log.info("  → 0 final matches after Stage 2")
                continue

            log.info("  → %d final match(es) stored", len(final_scores))

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
                total_matches += 1

        await db.commit()

    log.info("=" * 60)
    log.info(
        "MATCHING JOB DONE — %d match(es) stored | %d LLM call(s) | %d filtered by LLM",
        total_matches, total_llm_calls, total_llm_skipped,
    )
    log.info("=" * 60)

    import asyncio
    from backend.services.seeder import export_fetched_paper_embeddings
    asyncio.create_task(export_fetched_paper_embeddings())


async def run_stage2_for_unmatched() -> None:
    """Run Stage 1+2 for fetched papers that have embeddings but no researcher matches."""
    global _job_running
    if _job_running:
        log.warning("A job is already running — skipping rematch trigger.")
        return
    _job_running = True
    try:
        await _run_stage2_for_unmatched_impl()
    finally:
        _job_running = False


async def _run_stage2_for_unmatched_impl() -> None:
    import asyncio
    from backend.database import SessionLocal
    from backend.models import FetchedPaper, ResearcherPaper, PaperResearcherMatch, Researcher
    from backend.services.embedding import encode_with_fallback, batch_score, emb_to_list, row_to_emb
    from sqlalchemy import select, text as sa_text

    log.info("=" * 60)
    log.info("REMATCH JOB — finding unmatched papers …")

    async with SessionLocal() as db:
        rows = list(await db.execute(
            sa_text(
                "SELECT openalex_id, title, abstract, concepts_text, embedding "
                "FROM fetched_papers fp "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM paper_researcher_matches m WHERE m.paper_openalex_id = fp.openalex_id"
                ") ORDER BY openalex_id"
            )
        ))

    if not rows:
        log.info("REMATCH JOB — no unmatched papers found.")
        return

    log.info("REMATCH JOB — %d unmatched paper(s) found.", len(rows))

    # Split into papers with and without embeddings
    to_encode = [r for r in rows if r.embedding is None]
    already_embedded = [r for r in rows if r.embedding is not None]

    all_papers = []
    all_embs_list = []

    # Re-encode papers without embeddings
    if to_encode:
        log.info("REMATCH JOB — encoding %d paper(s) without embeddings …", len(to_encode))
        texts = [f"{r.title or ''} {r.abstract or ''} {r.concepts_text or ''}".strip() for r in to_encode]
        try:
            embs = await asyncio.to_thread(encode_with_fallback, texts, RETRIEVE_MODEL, OLLAMA_URL)
        except Exception as e:
            log.error("REMATCH JOB — encoding failed: %s", e)
            return
        async with SessionLocal() as db:
            for r, emb in zip(to_encode, embs):
                vec_str = "[" + ",".join(f"{float(x):.8g}" for x in emb) + "]"
                await db.execute(
                    sa_text(f"UPDATE fetched_papers SET embedding = '{vec_str}' WHERE openalex_id = :oid"),
                    {"oid": r.openalex_id},
                )
            await db.commit()
        for r, emb in zip(to_encode, embs):
            all_papers.append({"openalex_id": r.openalex_id, "title": r.title, "abstract": r.abstract})
            all_embs_list.append(emb)

    for r in already_embedded:
        all_papers.append({"openalex_id": r.openalex_id, "title": r.title, "abstract": r.abstract})
        all_embs_list.append(row_to_emb(r.embedding))

    fetched_embs = np.vstack(all_embs_list)

    # Load BOUN paper embeddings
    async with SessionLocal() as db:
        boun_rows = list(await db.execute(
            select(ResearcherPaper.researcher_id, ResearcherPaper.paper_openalex_id,
                   ResearcherPaper.title, ResearcherPaper.abstract, ResearcherPaper.embedding)
            .where(ResearcherPaper.embedding.isnot(None))
        ))

    if not boun_rows:
        log.warning("REMATCH JOB — no BOUN embeddings, aborting.")
        return

    boun_embs = np.vstack([row_to_emb(r.embedding) for r in boun_rows])
    scores_matrix = batch_score(fetched_embs, boun_embs)
    log.info("REMATCH JOB — similarity matrix %s computed.", scores_matrix.shape)

    total_matches = 0
    total_llm_calls = 0
    total_llm_skipped = 0

    async with SessionLocal() as db:
        for i, paper in enumerate(all_papers):
            paper_scores = scores_matrix[i]
            researcher_hits: dict[str, list[tuple[float, object]]] = {}
            for j, boun_row in enumerate(boun_rows):
                score = float(paper_scores[j])
                if score < MATCH_THRESHOLD:
                    continue
                researcher_hits.setdefault(boun_row.researcher_id, []).append((score, boun_row))

            if not researcher_hits:
                continue

            researcher_ranked = {
                r_id: sorted(hits, key=lambda x: x[0], reverse=True)
                for r_id, hits in researcher_hits.items()
            }
            researcher_best = {r_id: hits[0][0] for r_id, hits in researcher_ranked.items()}
            top_researchers = sorted(researcher_best.items(), key=lambda x: x[1], reverse=True)[:RAG_RETRIEVE_TOP_K]

            final_scores: dict[str, tuple[float, list, float | None]] = {}
            for r_id, emb_score in top_researchers:
                hits = researcher_ranked[r_id]
                llm_score: float | None = None
                if len(final_scores) < RAG_LLM_TOP_K:
                    llm_score = await asyncio.to_thread(_llm_generate, paper, hits[:RAG_CONTEXT_PAPERS])
                    total_llm_calls += 1
                    if llm_score == 0.0:
                        total_llm_skipped += 1
                        continue
                    final_score = llm_score if llm_score is not None else emb_score
                else:
                    final_score = emb_score

                if final_score >= MATCH_THRESHOLD:
                    final_scores[r_id] = (final_score, hits, llm_score)

            import json
            for r_id, (final_score, hits, llm_score) in final_scores.items():
                matched_ids_json = json.dumps([
                    {"id": row.paper_openalex_id, "score": round(float(score), 4)}
                    for score, row in hits[:RAG_CONTEXT_PAPERS]
                ])
                db.add(PaperResearcherMatch(
                    paper_openalex_id=paper["openalex_id"],
                    researcher_id=r_id,
                    score=round(final_score, 4),
                    model="qwen+llama",
                    matched_paper_ids=matched_ids_json,
                    llm_score=round(llm_score, 4) if llm_score is not None else None,
                ))
                total_matches += 1

        await db.commit()

    log.info("REMATCH JOB DONE — %d match(es) stored | %d LLM call(s) | %d filtered by LLM",
             total_matches, total_llm_calls, total_llm_skipped)


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
        log.warning("LLM generate step failed: %s — falling back to Stage 1 score.", e)
        return None
