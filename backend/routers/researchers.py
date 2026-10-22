from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User, Researcher, PaperResearcherMatch, FetchedPaper, BounWork, BounAuthorship
from backend.config import EMBEDDING_VERSION
from backend.schemas import (
    ResearcherOut, ResearchersResponse, ResearcherDetailOut, ResearcherMergedOut, MatchedPaperForResearcher,
    ResearcherProfile, RecentWork, Coauthor,
)

router = APIRouter(prefix="/researchers", tags=["researchers"])


async def researcher_profile(db: AsyncSession, researcher_ids: list[str]) -> ResearcherProfile:
    """Topics, recent works and frequent Boğaziçi co-authors of one person (several ids if split)."""
    works = select(BounAuthorship.work_id).where(BounAuthorship.researcher_id.in_(researcher_ids))

    topics = [t for t, in await db.execute(
        select(BounWork.primary_topic)
        .where(BounWork.openalex_id.in_(works), BounWork.primary_topic.isnot(None))
        .group_by(BounWork.primary_topic)
        .order_by(func.count().desc(), BounWork.primary_topic)
        .limit(5)
    )]
    recent = [
        RecentWork(work_id=w.openalex_id, title=w.title, year=w.first_date.year if w.first_date else None)
        for w in await db.scalars(
            select(BounWork).where(BounWork.openalex_id.in_(works))
            .order_by(BounWork.first_date.desc().nulls_last()).limit(5)
        )
    ]
    # Co-authorship through collaborations says little, so 100+-author works are left out.
    small_works = select(BounWork.openalex_id).where(BounWork.openalex_id.in_(works), BounWork.large_collaboration.is_(False))
    coauthors = [
        Coauthor(id=rid, display_name=name, shared_works=n)
        for rid, name, n in await db.execute(
            select(Researcher.id, Researcher.display_name, func.count())
            .join(BounAuthorship, BounAuthorship.researcher_id == Researcher.id)
            .where(BounAuthorship.work_id.in_(small_works), Researcher.id.notin_(researcher_ids))
            .group_by(Researcher.id, Researcher.display_name)
            .order_by(func.count().desc(), Researcher.display_name)
            .limit(6)
        )
    ]
    return ResearcherProfile(topics=topics, recent_works=recent, coauthors=coauthors)


@router.get("", response_model=ResearchersResponse)
async def list_researchers(
    q: str = Query("", description="Search by name"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Researcher)
    count_q = select(func.count(Researcher.id))

    if q.strip():
        pattern = f"%{q.strip()}%"
        base = base.where(Researcher.display_name.ilike(pattern))
        count_q = count_q.where(Researcher.display_name.ilike(pattern))

    total = await db.scalar(count_q) or 0
    offset = (page - 1) * limit

    rows = await db.scalars(
        base.order_by(Researcher.display_name).offset(offset).limit(limit)
    )
    researchers = list(rows)

    return ResearchersResponse(
        researchers=researchers,
        total=total,
        page=page,
        pages=math.ceil(total / limit) if total else 0,
    )


@router.get("/by-name", response_model=ResearcherMergedOut)
async def get_researcher_by_name(
    name: str = Query(..., description="Exact display name"),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    researchers = list(await db.scalars(
        select(Researcher).where(func.lower(Researcher.display_name) == name.lower().strip())
    ))
    if not researchers:
        raise HTTPException(status_code=404, detail="Researcher not found")

    researcher_ids = [r.id for r in researchers]

    rows = await db.execute(
        select(PaperResearcherMatch, FetchedPaper)
        .join(FetchedPaper, PaperResearcherMatch.paper_openalex_id == FetchedPaper.openalex_id)
        .where(PaperResearcherMatch.researcher_id.in_(researcher_ids), PaperResearcherMatch.embedding_version == EMBEDDING_VERSION)
        .order_by(PaperResearcherMatch.score.desc())
        .limit(50)
    )

    seen_papers: set[str] = set()
    matched_papers = []
    for match, paper in rows:
        key = (paper.title or paper.openalex_id).lower().strip()
        if key in seen_papers:
            continue
        seen_papers.add(key)
        matched_papers.append(MatchedPaperForResearcher(
            openalex_id=paper.openalex_id,
            title=paper.title,
            publication_date=paper.publication_date,
            source_institution_name=paper.source_institution_name,
            score=round(match.score, 4),
        ))

    total_matches = await db.scalar(
        select(func.count(PaperResearcherMatch.paper_openalex_id))
        .where(PaperResearcherMatch.researcher_id.in_(researcher_ids), PaperResearcherMatch.embedding_version == EMBEDDING_VERSION)
    ) or 0

    return ResearcherMergedOut(
        **(await researcher_profile(db, researcher_ids)).model_dump(),
        display_name=researchers[0].display_name,
        ids=[r.id for r in researchers],
        openalex_urls=[r.openalex_id for r in researchers],
        total_papers=sum(r.paper_count for r in researchers),
        matched_papers=matched_papers,
        total_matches=total_matches,
    )


@router.get("/{researcher_id}", response_model=ResearcherDetailOut)
async def get_researcher(
    researcher_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    researcher = await db.get(Researcher, researcher_id)
    if not researcher:
        raise HTTPException(status_code=404, detail="Researcher not found")

    total_matches = await db.scalar(
        select(func.count(PaperResearcherMatch.paper_openalex_id))
        .where(PaperResearcherMatch.researcher_id == researcher_id, PaperResearcherMatch.embedding_version == EMBEDDING_VERSION)
    ) or 0

    offset = (page - 1) * limit
    rows = await db.execute(
        select(PaperResearcherMatch, FetchedPaper)
        .join(FetchedPaper, PaperResearcherMatch.paper_openalex_id == FetchedPaper.openalex_id)
        .where(PaperResearcherMatch.researcher_id == researcher_id, PaperResearcherMatch.embedding_version == EMBEDDING_VERSION)
        .order_by(PaperResearcherMatch.score.desc())
        .offset(offset)
        .limit(limit)
    )

    matched_papers = [
        MatchedPaperForResearcher(
            openalex_id=paper.openalex_id,
            title=paper.title,
            publication_date=paper.publication_date,
            source_institution_name=paper.source_institution_name,
            score=round(match.score, 4),
        )
        for match, paper in rows
    ]

    return ResearcherDetailOut(
        **(await researcher_profile(db, [researcher_id])).model_dump(),
        id=researcher.id,
        openalex_id=researcher.openalex_id,
        display_name=researcher.display_name,
        paper_count=researcher.paper_count,
        matched_papers=matched_papers,
        total_matches=total_matches,
        page=page,
        pages=math.ceil(total_matches / limit) if total_matches else 0,
    )
