from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User, UserFollow, FetchedPaper, PaperResearcherMatch, Researcher
from backend.schemas import PapersResponse, PaperOut, ResearcherMatch
from backend.config import TOP_K_MATCHES, MATCH_THRESHOLD

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("", response_model=PapersResponse)
async def get_papers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get followed institution IDs
    follows = await db.scalars(
        select(UserFollow.institution_openalex_id).where(UserFollow.user_id == current_user.id)
    )
    institution_ids = list(follows)

    if not institution_ids:
        return PapersResponse(papers=[], total=0, page=page, pages=0)

    # Count total
    total = await db.scalar(
        select(func.count(FetchedPaper.openalex_id)).where(
            FetchedPaper.source_institution_id.in_(institution_ids)
        )
    )

    # Fetch paginated papers
    offset = (page - 1) * limit
    paper_rows = await db.scalars(
        select(FetchedPaper)
        .where(FetchedPaper.source_institution_id.in_(institution_ids))
        .order_by(FetchedPaper.publication_date.desc().nullslast(), FetchedPaper.fetched_at.desc())
        .offset(offset)
        .limit(limit)
    )
    papers = list(paper_rows)

    # Fetch top researcher matches for each paper
    paper_ids = [p.openalex_id for p in papers]
    match_rows = await db.execute(
        select(PaperResearcherMatch, Researcher.display_name)
        .join(Researcher, PaperResearcherMatch.researcher_id == Researcher.id)
        .where(
            PaperResearcherMatch.paper_openalex_id.in_(paper_ids),
            PaperResearcherMatch.score >= MATCH_THRESHOLD,
        )
        .order_by(PaperResearcherMatch.paper_openalex_id, PaperResearcherMatch.score.desc())
    )

    # Group matches by paper
    matches_by_paper: dict[str, list[ResearcherMatch]] = {pid: [] for pid in paper_ids}
    for match, display_name in match_rows:
        bucket = matches_by_paper[match.paper_openalex_id]
        if len(bucket) < TOP_K_MATCHES:
            bucket.append(ResearcherMatch(display_name=display_name, score=round(match.score, 4)))

    out = [
        PaperOut(
            openalex_id=p.openalex_id,
            title=p.title,
            abstract=p.abstract,
            publication_date=p.publication_date,
            source_institution_name=p.source_institution_name,
            top_researchers=matches_by_paper.get(p.openalex_id, []),
        )
        for p in papers
    ]

    return PapersResponse(
        papers=out,
        total=total or 0,
        page=page,
        pages=math.ceil((total or 0) / limit),
    )
