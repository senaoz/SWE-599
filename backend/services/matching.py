from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import numpy as np

from backend.config import (
    MATCH_THRESHOLD,
    MATCH_AGGREGATION,
    EMBEDDING_VERSION,
    RETRIEVE_WORKS,
    RAG_RETRIEVE_TOP_K,
    RAG_CONTEXT_PAPERS,
)
from backend.services.ranking import rank_from_works

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
    from backend.services.seeder import normalize_doi
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
                        "(openalex_id, doi, title, abstract, concepts_text, publication_date, type, field, oa_url, "
                        "source_institution_id, source_institution_name) "
                        "VALUES (:oid, :doi, :title, :abstract, :concepts, :pub_date, :type, :field, :oa_url, "
                        ":inst_id, :inst_name) "
                        "ON CONFLICT (openalex_id) DO NOTHING"
                    ),
                    {
                        "oid": p["openalex_id"],
                        "doi": normalize_doi(p.get("doi")),
                        "title": p.get("title"),
                        "abstract": p.get("abstract"),
                        "concepts": p.get("concepts_text"),
                        "pub_date": p.get("publication_date"),
                        "type": p.get("type"),
                        "field": p.get("field"),
                        "oa_url": p.get("oa_url"),
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

    # Pick up papers that were never encoded (crashed runs) or were encoded with another version
    async with SessionLocal() as db:
        unembedded = list(await db.execute(
            select(FetchedPaper.openalex_id, FetchedPaper.doi, FetchedPaper.title, FetchedPaper.abstract)
            .where(FetchedPaper.embedding_version.is_distinct_from(EMBEDDING_VERSION))
        ))
    new_ids = {p["openalex_id"] for p in all_new_papers}
    extra = [_as_paper(r) for r in unembedded if r.openalex_id not in new_ids]
    if extra:
        log.info("Found %d earlier paper(s) without a current embedding — adding to batch.", len(extra))
        all_new_papers += extra

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
    from backend.models import FetchedPaper
    from backend.services.embedding import row_to_emb
    from sqlalchemy import text as sa_text

    log.info("=" * 60)
    log.info("REMATCH JOB — finding unmatched papers …")

    async with SessionLocal() as db:
        rows = list(await db.execute(
            sa_text(
                "SELECT openalex_id, doi, title, abstract, embedding, embedding_version "
                "FROM fetched_papers fp "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM paper_researcher_matches m "
                "  WHERE m.paper_openalex_id = fp.openalex_id AND m.embedding_version = :v"
                ") ORDER BY openalex_id"
            ).columns(embedding=FetchedPaper.embedding.type),
            {"v": EMBEDDING_VERSION},
        ))

    if not rows:
        log.info("REMATCH JOB — no unmatched papers found.")
        return

    log.info("REMATCH JOB — %d unmatched paper(s) found.", len(rows))

    current = [r for r in rows if r.embedding is not None and r.embedding_version == EMBEDDING_VERSION]
    current_ids = {r.openalex_id for r in current}
    to_encode = [_as_paper(r) for r in rows if r.openalex_id not in current_ids]

    papers: list[dict] = []
    embs_list: list[np.ndarray] = []
    if to_encode:
        embs = await _embed_and_store(to_encode, "REMATCH")
        if embs is None:
            return
        papers += to_encode
        embs_list += list(embs)
    for r in current:
        papers.append(_as_paper(r))
        embs_list.append(row_to_emb(r.embedding))

    total_matches = await _match_and_store(papers, np.vstack(embs_list), "REMATCH")
    if total_matches is not None:
        log.info("REMATCH JOB DONE — %d match(es) stored", total_matches)


def _as_paper(r) -> dict:
    return {"openalex_id": r.openalex_id, "doi": r.doi, "title": r.title, "abstract": r.abstract}


async def _embed_and_store(papers: list[dict], job: str) -> np.ndarray | None:
    """Embed papers and write the vectors to fetched_papers. Returns None if encoding fails."""
    import asyncio
    from backend.database import SessionLocal
    from backend.models import FetchedPaper
    from backend.services.embedding import encode, emb_to_list, paper_text
    from sqlalchemy import update

    log.info("%s — encoding %d paper(s) …", job, len(papers))
    try:
        embs = await asyncio.to_thread(encode, [paper_text(p.get("title"), p.get("abstract")) for p in papers])
    except Exception as e:
        log.error("%s — encoding failed (%s) — aborting. Is the encoder running?", job, e)
        return None

    async with SessionLocal() as db:
        for paper, emb in zip(papers, embs):
            await db.execute(
                update(FetchedPaper)
                .where(FetchedPaper.openalex_id == paper["openalex_id"])
                .values(embedding=emb_to_list(emb), embedding_version=EMBEDDING_VERSION)
            )
        await db.commit()
    log.info("%s — stored %d paper embeddings", job, len(papers))
    return embs


# Exact cosine search over the BOUN index at the current version, without the paper itself (D6):
# the same OpenAlex id, a merged duplicate of it, or the same DOI.
_SEARCH_SQL = """
    SELECT openalex_id, 1 - (embedding <=> :q) AS cosine
    FROM boun_works
    WHERE embedding_version = :v
      AND openalex_id <> :pid
      AND NOT (:pid = ANY(duplicate_ids))
      AND (CAST(:doi AS text) IS NULL OR doi IS DISTINCT FROM CAST(:doi AS text))
    ORDER BY embedding <=> :q
    LIMIT :k
"""


async def _match_and_store(papers: list[dict], paper_embs: np.ndarray, job: str) -> int | None:
    """Retrieve BOUN works for each paper, rank their researchers and store the top matches with
    their evidence. Returns the number of matches stored, or None if the BOUN index is empty."""
    from backend.database import SessionLocal
    from backend.models import BounWork, BounAuthorship, PaperResearcherMatch, MatchEvidence
    from backend.services.embedding import emb_to_list
    from backend.services.seeder import normalize_doi
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import select, delete, func, text as sa_text, bindparam

    search = sa_text(_SEARCH_SQL).bindparams(bindparam("q", type_=Vector(paper_embs.shape[1])))

    async with SessionLocal() as db:
        indexed = await db.scalar(
            select(func.count(BounWork.openalex_id)).where(BounWork.embedding_version == EMBEDDING_VERSION)
        )
        if not indexed:
            log.warning("%s — no BOUN works embedded at %s (seeder may still be running) — aborting.",
                        job, EMBEDDING_VERSION)
            return None

        total = 0
        no_hits = 0
        for paper, emb in zip(papers, paper_embs):
            hits = [(r.openalex_id, float(r.cosine)) for r in await db.execute(search, {
                "q": emb_to_list(emb), "v": EMBEDDING_VERSION, "pid": paper["openalex_id"],
                "doi": normalize_doi(paper.get("doi")), "k": RETRIEVE_WORKS,
            })]
            authors: dict[str, list[str]] = {}
            for wid, r_id in await db.execute(
                select(BounAuthorship.work_id, BounAuthorship.researcher_id)
                .where(BounAuthorship.work_id.in_([w for w, _ in hits]))
            ):
                authors.setdefault(wid, []).append(r_id)

            ranked = rank_from_works(hits, authors, MATCH_THRESHOLD, RAG_RETRIEVE_TOP_K, MATCH_AGGREGATION)

            await db.execute(delete(PaperResearcherMatch).where(
                PaperResearcherMatch.paper_openalex_id == paper["openalex_id"],
                PaperResearcherMatch.embedding_version == EMBEDDING_VERSION,
            ))
            if not ranked:
                no_hits += 1
                continue
            for rank, (r_id, score, r_hits) in enumerate(ranked, start=1):
                db.add(PaperResearcherMatch(
                    paper_openalex_id=paper["openalex_id"], researcher_id=r_id,
                    embedding_version=EMBEDDING_VERSION, score=round(score, 4), rank=rank,
                ))
            await db.flush()
            for r_id, _, r_hits in ranked:
                for cos, wid in r_hits[:RAG_CONTEXT_PAPERS]:
                    db.add(MatchEvidence(
                        paper_openalex_id=paper["openalex_id"], researcher_id=r_id,
                        embedding_version=EMBEDDING_VERSION, work_id=wid, score=round(cos, 4),
                    ))
            total += len(ranked)
        await db.commit()

    log.info(
        "%s — %d paper(s) against %d BOUN works: %d match(es), %d paper(s) with no researcher above %.2f",
        job, len(papers), indexed, total, no_hits, MATCH_THRESHOLD,
    )
    return total
