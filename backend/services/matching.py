from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

import numpy as np

from backend.config import (
    MATCH_THRESHOLD,
    MATCH_AGGREGATION,
    OLLAMA_URL,
    RETRIEVE_MODEL,
    RAG_RETRIEVE_TOP_K,
    RAG_CONTEXT_PAPERS,
)
from backend.services.ranking import match_papers

log = logging.getLogger(__name__)

_main_job_running = False
_rematch_job_running = False


async def run_matching_job() -> None:
    global _main_job_running
    if _main_job_running:
        log.warning("A job is already running — skipping this trigger.")
        return
    _main_job_running = True
    try:
        await _run_matching_job_impl()
    finally:
        _main_job_running = False


async def _run_matching_job_impl() -> None:
    from backend.database import SessionLocal
    from backend.models import UserFollow, FetchCursor, FetchedPaper
    from backend.services.openalex import fetch_new_papers
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

    embs = await _embed_and_store(all_new_papers, "MATCHING")
    if embs is None:
        return
    total_matches = await _match_and_store(all_new_papers, embs, "MATCHING")
    if total_matches is None:
        return

    log.info("=" * 60)
    log.info("MATCHING JOB DONE — %d match(es) stored", total_matches)
    log.info("=" * 60)

    import asyncio
    from backend.services.seeder import export_fetched_paper_embeddings
    asyncio.create_task(export_fetched_paper_embeddings())


async def run_rematch_unmatched() -> None:
    """Match fetched papers that have no researcher matches, embedding them first if needed."""
    global _rematch_job_running
    if _rematch_job_running:
        log.warning("A rematch job is already running — skipping rematch trigger.")
        return
    _rematch_job_running = True
    try:
        await _run_rematch_unmatched_impl()
    finally:
        _rematch_job_running = False


async def _run_rematch_unmatched_impl() -> None:
    from backend.database import SessionLocal
    from backend.services.embedding import row_to_emb
    from sqlalchemy import text as sa_text

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

    def as_paper(r) -> dict:
        return {"openalex_id": r.openalex_id, "title": r.title, "abstract": r.abstract, "concepts_text": r.concepts_text}

    to_encode = [as_paper(r) for r in rows if r.embedding is None]
    already_embedded = [r for r in rows if r.embedding is not None]

    papers: list[dict] = []
    embs_list: list[np.ndarray] = []
    if to_encode:
        embs = await _embed_and_store(to_encode, "REMATCH")
        if embs is None:
            return
        papers += to_encode
        embs_list += list(embs)
    for r in already_embedded:
        papers.append(as_paper(r))
        embs_list.append(row_to_emb(r.embedding))

    total_matches = await _match_and_store(papers, np.vstack(embs_list), "REMATCH")
    if total_matches is not None:
        log.info("REMATCH JOB DONE — %d match(es) stored", total_matches)


def _paper_text(p: dict) -> str:
    return f"{p.get('title') or ''} {p.get('abstract') or ''} {p.get('concepts_text') or ''}".strip()


async def _embed_and_store(papers: list[dict], job: str) -> np.ndarray | None:
    """Embed papers and write the vectors to fetched_papers. Returns None if encoding fails."""
    import asyncio
    from backend.database import SessionLocal
    from backend.services.embedding import encode_checked
    from sqlalchemy import text as sa_text

    log.info("%s — encoding %d paper(s) with %s …", job, len(papers), RETRIEVE_MODEL)
    try:
        embs = await asyncio.to_thread(encode_checked, [_paper_text(p) for p in papers], RETRIEVE_MODEL, OLLAMA_URL)
    except Exception as e:
        log.error("%s — encoding failed (%s) — aborting. Is Ollama running at %s?", job, e, OLLAMA_URL)
        return None

    async with SessionLocal() as db:
        for paper, emb in zip(papers, embs):
            vec_str = "[" + ",".join(f"{float(x):.8g}" for x in emb) + "]"
            await db.execute(
                sa_text(f"UPDATE fetched_papers SET embedding = '{vec_str}' WHERE openalex_id = :oid"),
                {"oid": paper["openalex_id"]},
            )
        await db.commit()
    log.info("%s — stored %d paper embeddings", job, len(papers))
    return embs


async def _match_and_store(papers: list[dict], paper_embs: np.ndarray, job: str) -> int | None:
    """Rank BOUN researchers for each paper by cosine and store the top matches.

    Returns the number of matches stored, or None if no BOUN embeddings are loaded yet.
    """
    from backend.database import SessionLocal
    from backend.models import ResearcherPaper, PaperResearcherMatch
    from backend.services.embedding import OLLAMA_MODEL_MAP, row_to_emb
    from sqlalchemy import select

    async with SessionLocal() as db:
        boun_rows = list(await db.execute(
            select(ResearcherPaper.researcher_id, ResearcherPaper.paper_openalex_id, ResearcherPaper.embedding)
            .where(ResearcherPaper.embedding.isnot(None))
        ))
    if not boun_rows:
        log.warning("%s — no BOUN paper embeddings found (seeder may still be running) — aborting.", job)
        return None

    boun_embs = np.vstack([row_to_emb(r.embedding) for r in boun_rows])
    researcher_ids = [r.researcher_id for r in boun_rows]
    results = match_papers(paper_embs, boun_embs, researcher_ids, MATCH_THRESHOLD, RAG_RETRIEVE_TOP_K, MATCH_AGGREGATION)
    model_label = OLLAMA_MODEL_MAP[RETRIEVE_MODEL]

    total = 0
    no_hits = 0
    async with SessionLocal() as db:
        for paper, ranked in zip(papers, results):
            if not ranked:
                no_hits += 1
                continue
            for r_id, score, hits in ranked:
                db.add(PaperResearcherMatch(
                    paper_openalex_id=paper["openalex_id"],
                    researcher_id=r_id,
                    score=round(score, 4),
                    model=model_label,
                    matched_paper_ids=json.dumps([
                        {"id": boun_rows[j].paper_openalex_id, "score": round(s, 4)}
                        for s, j in hits[:RAG_CONTEXT_PAPERS]
                    ]),
                ))
                total += 1
        await db.commit()

    log.info(
        "%s — %d paper(s) against %d BOUN rows: %d match(es), %d paper(s) with no researcher above %.2f",
        job, len(papers), len(boun_rows), total, no_hits, MATCH_THRESHOLD,
    )
    return total
