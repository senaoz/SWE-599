from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import hash_password, verify_password, create_access_token, get_current_user
from backend.database import get_db
from backend.models import User, Researcher, UserFavoriteResearcher
from backend.schemas import RegisterRequest, LoginRequest, TokenResponse, MeResponse, ResearcherBrief

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.id))


async def _me(user: User, db: AsyncSession) -> MeResponse:
    favorites = await db.scalars(
        select(Researcher)
        .join(UserFavoriteResearcher, UserFavoriteResearcher.researcher_id == Researcher.id)
        .where(UserFavoriteResearcher.user_id == user.id)
        .order_by(Researcher.display_name)
    )
    return MeResponse(
        email=user.email,
        is_admin=user.is_admin,
        favorites=[ResearcherBrief.model_validate(r) for r in favorites],
    )


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _me(user, db)


@router.put("/me/favorites/{researcher_id}", response_model=MeResponse)
async def add_favorite(researcher_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Add a Boğaziçi researcher to the user's favourites, which drive the For me feed."""
    if not await db.get(Researcher, researcher_id):
        raise HTTPException(status_code=404, detail="Researcher not found")
    await db.execute(
        pg_insert(UserFavoriteResearcher)
        .values(user_id=user.id, researcher_id=researcher_id)
        .on_conflict_do_nothing()
    )
    await db.commit()
    return await _me(user, db)


@router.delete("/me/favorites/{researcher_id}", response_model=MeResponse)
async def remove_favorite(researcher_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(UserFavoriteResearcher).where(
        UserFavoriteResearcher.user_id == user.id, UserFavoriteResearcher.researcher_id == researcher_id,
    ))
    await db.commit()
    return await _me(user, db)
