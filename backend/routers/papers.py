from __future__ import annotations

import json
import math
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User, UserFollow, FetchedPaper, PaperResearcherMatch, Researcher, ResearcherPaper, UserPaperView
from backend.schemas import PapersResponse, PaperOut, PaperDetailOut, ResearcherMatch, MatchedBounPaper
from fastapi import HTTPException
from backend.config import TOP_K_MATCHES, MATCH_THRESHOLD

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("", response_model=PapersResponse)
async def get_papers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    institution_id: str | None = Query(None, description="Filter by institution OpenAlex ID"),
    from_date: date | None = Query(None, description="Filter papers published on or after this date"),
    to_date: date | None = Query(None, description="Filter papers published on or before this date"),
    min_score: float = Query(MATCH_THRESHOLD, ge=0.0, le=1.0, description="Minimum researcher match score"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    follows = await db.scalars(
        select(UserFollow.institution_openalex_id).where(UserFollow.user_id == current_user.id)
    )
    institution_ids = list(follows)

    if not institution_ids:
        return PapersResponse(papers=[], total=0, page=page, pages=0)

    # Apply institution filter
    if institution_id and institution_id in institution_ids:
        active_ids = [institution_id]
    else:
        active_ids = institution_ids

    # Build WHERE clause for DISTINCT ON dedup queries
    conditions = ["source_institution_id = ANY(:inst_ids)"]
    params: dict = {"inst_ids": active_ids}

    if from_date:
        conditions.append("publication_date >= :from_date")
        params["from_date"] = from_date
    if to_date:
        conditions.append("publication_date <= :to_date")
        params["to_date"] = to_date

    where_sql = " AND ".join(conditions)

    # Count distinct by title (dedup)
    total = await db.scalar(text(f"""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT ON (COALESCE(lower(title), openalex_id)) openalex_id
            FROM fetched_papers WHERE {where_sql}
        ) t
    """), params)

    offset = (page - 1) * limit
    rows = await db.execute(text(f"""
        SELECT openalex_id, title, abstract, publication_date,
               source_institution_id, source_institution_name
        FROM (
            SELECT DISTINCT ON (COALESCE(lower(title), openalex_id))
                openalex_id, title, abstract, publication_date,
                source_institution_id, source_institution_name, fetched_at
            FROM fetched_papers WHERE {where_sql}
            ORDER BY COALESCE(lower(title), openalex_id),
                     publication_date DESC NULLS LAST, fetched_at DESC
        ) t
        ORDER BY publication_date DESC NULLS LAST, fetched_at DESC
        LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": offset})

    papers = rows.mappings().all()

    paper_ids = [p["openalex_id"] for p in papers]
    match_rows = await db.execute(
        select(PaperResearcherMatch, Researcher.display_name)
        .join(Researcher, PaperResearcherMatch.researcher_id == Researcher.id)
        .where(
            PaperResearcherMatch.paper_openalex_id.in_(paper_ids),
            PaperResearcherMatch.score >= min_score,
        )
        .order_by(PaperResearcherMatch.paper_openalex_id, PaperResearcherMatch.score.desc())
    )
    match_list = list(match_rows)

    all_boun_ids: list[str] = []
    parsed_matches: list[tuple] = []
    for match, display_name in match_list:
        items: list[dict] = json.loads(match.matched_paper_ids or "[]")
        for item in items:
            all_boun_ids.append(item["id"])
        parsed_matches.append((match, display_name, items))

    boun_title_map: dict[str, str | None] = {}
    if all_boun_ids:
        title_rows = await db.execute(
            select(ResearcherPaper.paper_openalex_id, ResearcherPaper.title)
            .where(ResearcherPaper.paper_openalex_id.in_(all_boun_ids))
            .distinct()
        )
        boun_title_map = {row.paper_openalex_id: row.title for row in title_rows}

    # Fetch which papers this user has already seen
    seen_rows = await db.scalars(
        select(UserPaperView.paper_openalex_id).where(
            UserPaperView.user_id == current_user.id,
            UserPaperView.paper_openalex_id.in_(paper_ids),
        )
    )
    seen_ids: set[str] = set(seen_rows)

    matches_by_paper: dict[str, list[ResearcherMatch]] = {pid: [] for pid in paper_ids}
    seen_names_by_paper: dict[str, set[str]] = {pid: set() for pid in paper_ids}
    for match, display_name, items in parsed_matches:
        bucket = matches_by_paper[match.paper_openalex_id]
        seen_names = seen_names_by_paper[match.paper_openalex_id]
        if len(bucket) >= TOP_K_MATCHES or display_name in seen_names:
            continue
        seen_names.add(display_name)

        matched_papers = [
            MatchedBounPaper(title=boun_title_map.get(item["id"]), score=item["score"])
            for item in items
            if boun_title_map.get(item["id"])
        ]
        bucket.append(ResearcherMatch(
            researcher_id=match.researcher_id,
            display_name=display_name,
            score=round(match.score, 4),
            matched_papers=matched_papers,
        ))

    out = [
        PaperOut(
            openalex_id=p["openalex_id"],
            title=p["title"],
            abstract=p["abstract"],
            publication_date=p["publication_date"],
            source_institution_name=p["source_institution_name"],
            top_researchers=matches_by_paper.get(p["openalex_id"], []),
            is_seen=p["openalex_id"] in seen_ids,
        )
        for p in papers
    ]

    return PapersResponse(
        papers=out,
        total=total or 0,
        page=page,
        pages=math.ceil((total or 0) / limit),
    )


@router.get("/{paper_id}", response_model=PaperDetailOut)
async def get_paper_detail(
    paper_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    full_id = f"https://openalex.org/{paper_id}"
    paper = await db.get(FetchedPaper, full_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    match_rows = await db.execute(
        select(PaperResearcherMatch, Researcher.display_name)
        .join(Researcher, PaperResearcherMatch.researcher_id == Researcher.id)
        .where(PaperResearcherMatch.paper_openalex_id == full_id)
        .order_by(PaperResearcherMatch.score.desc())
    )
    match_list = list(match_rows)

    all_boun_ids: list[str] = []
    parsed: list[tuple] = []
    for match, display_name in match_list:
        items: list[dict] = json.loads(match.matched_paper_ids or "[]")
        for item in items:
            all_boun_ids.append(item["id"])
        parsed.append((match, display_name, items))

    boun_title_map: dict[str, str | None] = {}
    if all_boun_ids:
        rows = await db.execute(
            select(ResearcherPaper.paper_openalex_id, ResearcherPaper.title)
            .where(ResearcherPaper.paper_openalex_id.in_(all_boun_ids))
            .distinct()
        )
        boun_title_map = {r.paper_openalex_id: r.title for r in rows}

    all_researchers = [
        ResearcherMatch(
            researcher_id=match.researcher_id,
            display_name=display_name,
            score=round(match.score, 4),
            matched_papers=[
                MatchedBounPaper(title=boun_title_map.get(item["id"]), score=item["score"])
                for item in items if boun_title_map.get(item["id"])
            ],
        )
        for match, display_name, items in parsed
    ]

    return PaperDetailOut(
        openalex_id=paper.openalex_id,
        title=paper.title,
        abstract=paper.abstract,
        publication_date=paper.publication_date,
        source_institution_name=paper.source_institution_name,
        all_researchers=all_researchers,
    )


@router.post("/{paper_id}/seen", status_code=204)
async def mark_seen(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    full_id = f"https://openalex.org/{paper_id}"
    existing = await db.get(UserPaperView, (current_user.id, full_id))
    if not existing:
        db.add(UserPaperView(user_id=current_user.id, paper_openalex_id=full_id))
        await db.commit()
