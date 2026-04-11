from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User, Researcher
from backend.schemas import ResearcherOut, ResearchersResponse

router = APIRouter(prefix="/researchers", tags=["researchers"])


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
