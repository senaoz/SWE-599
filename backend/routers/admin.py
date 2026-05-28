from __future__ import annotations

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from sqlalchemy import text
from backend.models import User, FetchedPaper, PaperResearcherMatch, Researcher, FetchCursor
from backend.schemas import AdminStatus

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status", response_model=AdminStatus)
async def get_status(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    paper_count = await db.scalar(select(func.count(FetchedPaper.openalex_id))) or 0
    match_count = await db.scalar(select(func.count()).select_from(PaperResearcherMatch)) or 0
    researcher_count = await db.scalar(select(func.count(Researcher.id))) or 0
    unmatched_count = await db.scalar(text(
        "SELECT COUNT(*) FROM fetched_papers fp "
        "WHERE NOT EXISTS (SELECT 1 FROM paper_researcher_matches m WHERE m.paper_openalex_id = fp.openalex_id)"
    )) or 0

    last_cursor = await db.scalar(
        select(FetchCursor.last_run_at).order_by(FetchCursor.last_run_at.desc()).limit(1)
    )

    return AdminStatus(
        paper_count=paper_count,
        match_count=match_count,
        researcher_count=researcher_count,
        unmatched_count=unmatched_count,
        last_run_at=last_cursor,
    )


@router.post("/trigger", status_code=202)
async def trigger_job(
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_user),
):
    from backend.services.matching import run_matching_job
    background_tasks.add_task(run_matching_job)
    return {"detail": "Matching job started"}


@router.post("/rematch-unmatched", status_code=202)
async def rematch_unmatched(
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-run Stage 2 matching for fetched papers that have no researcher matches."""
    from backend.services.matching import run_stage2_for_unmatched
    background_tasks.add_task(run_stage2_for_unmatched)
    return {"detail": "Rematch job started for unmatched papers"}
