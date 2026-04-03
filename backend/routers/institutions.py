from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User, UserFollow, FetchCursor
from backend.schemas import FollowRequest, FollowedInstitution, InstitutionSearchResult

router = APIRouter(prefix="/institutions", tags=["institutions"])


@router.get("/search", response_model=list[InstitutionSearchResult])
async def search_institutions(q: str, _: User = Depends(get_current_user)):
    from backend.services.openalex import search_institutions as oa_search
    return await oa_search(q)


@router.get("", response_model=list[FollowedInstitution])
async def list_followed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(UserFollow).where(UserFollow.user_id == current_user.id)
    )
    return list(rows)


@router.post("", response_model=FollowedInstitution, status_code=201)
async def follow_institution(
    body: FollowRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.get(UserFollow, (current_user.id, body.institution_openalex_id))
    if existing:
        raise HTTPException(status_code=409, detail="Already following")

    follow = UserFollow(
        user_id=current_user.id,
        institution_openalex_id=body.institution_openalex_id,
        institution_name=body.institution_name,
    )
    db.add(follow)

    # Ensure a fetch cursor exists for this institution (backfill 7 days)
    cursor = await db.get(FetchCursor, body.institution_openalex_id)
    if not cursor:
        cursor = FetchCursor(
            institution_openalex_id=body.institution_openalex_id,
            last_fetched_date=date.today() - timedelta(days=7),
        )
        db.add(cursor)

    await db.commit()
    await db.refresh(follow)
    return follow


@router.delete("/{institution_id}", status_code=204)
async def unfollow_institution(
    institution_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(UserFollow).where(
            UserFollow.user_id == current_user.id,
            UserFollow.institution_openalex_id == institution_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Not following this institution")
    await db.commit()
