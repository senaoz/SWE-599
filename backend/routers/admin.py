from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User, FetchedPaper, PaperResearcherMatch, Researcher, FetchCursor, SystemConfig
from backend.schemas import AdminStatus, ModelInfo, SetModelRequest
from backend.config import AVAILABLE_MODELS

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status", response_model=AdminStatus)
async def get_status(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    active_model = await db.scalar(
        select(SystemConfig.value).where(SystemConfig.key == "active_model")
    ) or "specter2"

    paper_count = await db.scalar(select(func.count(FetchedPaper.openalex_id))) or 0
    match_count = await db.scalar(select(func.count()).select_from(PaperResearcherMatch)) or 0
    researcher_count = await db.scalar(select(func.count(Researcher.id))) or 0

    last_cursor = await db.scalar(
        select(FetchCursor.last_run_at).order_by(FetchCursor.last_run_at.desc()).limit(1)
    )

    return AdminStatus(
        active_model=active_model,
        paper_count=paper_count,
        match_count=match_count,
        researcher_count=researcher_count,
        last_run_at=last_cursor,
    )


@router.get("/models", response_model=list[ModelInfo])
async def list_models(_: User = Depends(get_current_user)):
    return AVAILABLE_MODELS


@router.put("/models/active", status_code=204)
async def set_active_model(
    body: SetModelRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid_keys = {m["key"] for m in AVAILABLE_MODELS}
    if body.model not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Unknown model '{body.model}'")

    config = await db.get(SystemConfig, "active_model")
    if config:
        config.value = body.model
    else:
        db.add(SystemConfig(key="active_model", value=body.model))
    await db.commit()


@router.post("/trigger", status_code=202)
async def trigger_job(
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_user),
):
    from backend.services.matching import run_matching_job
    background_tasks.add_task(run_matching_job)
    return {"detail": "Matching job started"}
