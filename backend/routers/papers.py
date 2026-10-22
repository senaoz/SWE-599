from __future__ import annotations

import math
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.config import TOP_K_MATCHES, MATCH_THRESHOLD, EMBEDDING_VERSION
from backend.database import get_db
from backend.models import (
    User, UserFollow, FetchedPaper, PaperResearcherMatch, MatchEvidence, BounWork, Researcher,
    UserPaperView, PaperFeedback,
)
from backend.schemas import (
    PapersResponse, PaperOut, PaperDetailOut, ResearcherMatch, MatchedBounPaper, FieldCount,
)

router = APIRouter(prefix="/papers", tags=["papers"])

_PAPER_COLUMNS = (
    "openalex_id, title, abstract, publication_date, source_institution_id, "
    "source_institution_name, doi, type, field, oa_url"
)


async def load_matches(
    db: AsyncSession, paper_ids: list[str], user_id: int | None = None, min_score: float = 0.0,
) -> list[ResearcherMatch]:
    """Matches at the current embedding version, by paper and rank, with their matched BOUN works
    and, when `user_id` is given, that user's verdict on each."""
    if not paper_ids:
        return []
    match_rows = list(await db.execute(
        select(PaperResearcherMatch, Researcher.display_name)
        .join(Researcher, PaperResearcherMatch.researcher_id == Researcher.id)
        .where(
            PaperResearcherMatch.paper_openalex_id.in_(paper_ids),
            PaperResearcherMatch.embedding_version == EMBEDDING_VERSION,
            PaperResearcherMatch.score >= min_score,
        )
        .order_by(PaperResearcherMatch.paper_openalex_id, PaperResearcherMatch.rank)
    ))
    evidence: dict[tuple[str, str], list[MatchedBounPaper]] = {}
    for e, work in await db.execute(
        select(MatchEvidence, BounWork)
        .join(BounWork, MatchEvidence.work_id == BounWork.openalex_id)
        .where(
            MatchEvidence.paper_openalex_id.in_(paper_ids),
            MatchEvidence.embedding_version == EMBEDDING_VERSION,
        )
        .order_by(MatchEvidence.score.desc())
    ):
        if work.title:
            evidence.setdefault((e.paper_openalex_id, e.researcher_id), []).append(MatchedBounPaper(
                work_id=work.openalex_id,
                title=work.title,
                score=e.score,
                year=work.first_date.year if work.first_date else None,
                large_collaboration=work.large_collaboration,
            ))
    verdicts: dict[tuple[str, str], str] = {}
    if user_id is not None:
        verdicts = {
            (f.paper_openalex_id, f.researcher_id): f.verdict
            for f in await db.scalars(select(PaperFeedback).where(
                PaperFeedback.user_id == user_id, PaperFeedback.paper_openalex_id.in_(paper_ids),
            ))
        }
    return [
        ResearcherMatch(
            paper_openalex_id=m.paper_openalex_id,
            researcher_id=m.researcher_id,
            display_name=name,
            score=round(m.score, 4),
            rank=m.rank,
            matched_papers=evidence.get((m.paper_openalex_id, m.researcher_id), []),
            my_verdict=verdicts.get((m.paper_openalex_id, m.researcher_id)),
        )
        for m, name in match_rows
    ]


def _filters(
    institution_ids: list[str] | None, from_date: date | None, to_date: date | None, search: str | None,
    concept: str | None, field: str | None,
) -> tuple[list[str], dict]:
    conditions: list[str] = []
    params: dict = {}
    if institution_ids is not None:
        conditions.append("source_institution_id = ANY(:inst_ids)")
        params["inst_ids"] = institution_ids
    if from_date:
        conditions.append("publication_date >= :from_date")
        params["from_date"] = from_date
    if to_date:
        conditions.append("publication_date <= :to_date")
        params["to_date"] = to_date
    if search:
        conditions.append("(title ILIKE :search OR abstract ILIKE :search)")
        params["search"] = f"%{search}%"
    if concept:
        conditions.append("concepts_text ILIKE :concept")
        params["concept"] = f"%{concept}%"
    if field:
        conditions.append("field = :field")
        params["field"] = field
    return conditions, params


async def _page_of_papers(db: AsyncSession, conditions: list[str], params: dict, page: int, limit: int):
    """One page of papers, newest first, with exact-title duplicates collapsed."""
    where_sql = " AND ".join(conditions) or "TRUE"
    total = await db.scalar(text(f"""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT ON (COALESCE(lower(title), openalex_id)) openalex_id
            FROM fetched_papers WHERE {where_sql}
        ) t
    """), params) or 0
    rows = await db.execute(text(f"""
        SELECT {_PAPER_COLUMNS}
        FROM (
            SELECT DISTINCT ON (COALESCE(lower(title), openalex_id)) {_PAPER_COLUMNS}, fetched_at
            FROM fetched_papers WHERE {where_sql}
            ORDER BY COALESCE(lower(title), openalex_id), publication_date DESC NULLS LAST, fetched_at DESC
        ) t
        ORDER BY publication_date DESC NULLS LAST, fetched_at DESC
        LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": (page - 1) * limit})
    return total, rows.mappings().all()


async def _papers_response(
    db: AsyncSession, user: User, papers, total: int, page: int, limit: int, min_score: float,
) -> PapersResponse:
    paper_ids = [p["openalex_id"] for p in papers]
    seen_ids = set(await db.scalars(select(UserPaperView.paper_openalex_id).where(
        UserPaperView.user_id == user.id, UserPaperView.paper_openalex_id.in_(paper_ids),
    )))

    shown: dict[str, list[ResearcherMatch]] = {pid: [] for pid in paper_ids}
    mine: dict[str, ResearcherMatch] = {}
    names: dict[str, set[str]] = {pid: set() for pid in paper_ids}
    for m in await load_matches(db, paper_ids, user.id):
        if user.researcher_id and m.researcher_id == user.researcher_id:
            mine[m.paper_openalex_id] = m
        # Split author ids share a display name; show each name once.
        if m.score < min_score or len(shown[m.paper_openalex_id]) >= TOP_K_MATCHES or m.display_name in names[m.paper_openalex_id]:
            continue
        names[m.paper_openalex_id].add(m.display_name)
        shown[m.paper_openalex_id].append(m)

    return PapersResponse(
        papers=[
            PaperOut(
                **{k: p[k] for k in ("openalex_id", "title", "abstract", "publication_date",
                                     "source_institution_name", "doi", "type", "field", "oa_url")},
                top_researchers=shown[p["openalex_id"]],
                my_match=mine.get(p["openalex_id"]),
                is_seen=p["openalex_id"] in seen_ids,
            )
            for p in papers
        ],
        total=total,
        page=page,
        pages=math.ceil(total / limit),
    )


@router.get("", response_model=PapersResponse)
async def get_papers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    institution_id: str | None = Query(None, description="Filter by institution OpenAlex ID"),
    from_date: date | None = Query(None, description="Published on or after this date"),
    to_date: date | None = Query(None, description="Published on or before this date"),
    min_score: float = Query(MATCH_THRESHOLD, ge=0.0, le=1.0, description="Minimum researcher match score"),
    include_unmatched: bool = Query(True, description="Include papers with no researcher matches"),
    search: str | None = Query(None, description="Search in title and abstract"),
    concept: str | None = Query(None, description="Filter by concept/topic keyword"),
    field: str | None = Query(None, description="OpenAlex field of the paper's primary topic"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explore: papers from the institutions the user follows."""
    followed = list(await db.scalars(
        select(UserFollow.institution_openalex_id).where(UserFollow.user_id == current_user.id)
    ))
    if not followed:
        return PapersResponse(papers=[], total=0, page=page, pages=0)
    active = [institution_id] if institution_id in followed else followed

    conditions, params = _filters(active, from_date, to_date, search, concept, field)
    if not include_unmatched:
        conditions.append(
            "EXISTS (SELECT 1 FROM paper_researcher_matches m "
            "WHERE m.paper_openalex_id = fetched_papers.openalex_id AND m.embedding_version = :version)"
        )
        params["version"] = EMBEDDING_VERSION
    total, papers = await _page_of_papers(db, conditions, params, page, limit)
    return await _papers_response(db, current_user, papers, total, page, limit, min_score)


@router.get("/for-me", response_model=PapersResponse)
async def get_papers_for_me(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    search: str | None = Query(None),
    field: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Papers matched to the user's claimed Boğaziçi profile, from any institution in the database."""
    if not current_user.researcher_id:
        raise HTTPException(status_code=409, detail="No researcher profile claimed")
    conditions, params = _filters(None, from_date, to_date, search, None, field)
    conditions.append(
        "EXISTS (SELECT 1 FROM paper_researcher_matches m WHERE m.paper_openalex_id = fetched_papers.openalex_id "
        "AND m.embedding_version = :version AND m.researcher_id = :rid AND m.rank <= :top_k AND m.score >= :min_score)"
    )
    # Only papers where the researcher would be shown under the paper in Explore.
    params.update(version=EMBEDDING_VERSION, rid=current_user.researcher_id, top_k=TOP_K_MATCHES,
                  min_score=MATCH_THRESHOLD)
    total, papers = await _page_of_papers(db, conditions, params, page, limit)
    return await _papers_response(db, current_user, papers, total, page, limit, 0.0)


@router.get("/fields", response_model=list[FieldCount])
async def get_fields(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Fields of the papers from followed institutions, most common first."""
    followed = select(UserFollow.institution_openalex_id).where(UserFollow.user_id == current_user.id)
    rows = await db.execute(
        select(FetchedPaper.field, func.count())
        .where(FetchedPaper.field.isnot(None), FetchedPaper.source_institution_id.in_(followed))
        .group_by(FetchedPaper.field)
        .order_by(func.count().desc())
    )
    return [FieldCount(field=f, count=n) for f, n in rows]


@router.get("/{paper_id}", response_model=PaperDetailOut)
async def get_paper_detail(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    full_id = f"https://openalex.org/{paper_id}"
    paper = await db.get(FetchedPaper, full_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return PaperDetailOut(
        openalex_id=paper.openalex_id,
        title=paper.title,
        abstract=paper.abstract,
        publication_date=paper.publication_date,
        source_institution_name=paper.source_institution_name,
        doi=paper.doi,
        type=paper.type,
        field=paper.field,
        oa_url=paper.oa_url,
        all_researchers=await load_matches(db, [full_id], current_user.id),
    )


@router.post("/{paper_id}/seen", status_code=204)
async def mark_seen(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text(
            "INSERT INTO user_paper_views (user_id, paper_openalex_id) "
            "VALUES (:uid, :pid) ON CONFLICT DO NOTHING"
        ),
        {"uid": current_user.id, "pid": f"https://openalex.org/{paper_id}"},
    )
    await db.commit()
