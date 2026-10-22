from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import hash_password, verify_password, create_access_token, get_current_user
from backend.database import get_db
from backend.models import User, Researcher
from backend.schemas import RegisterRequest, LoginRequest, TokenResponse, MeResponse, ResearcherBrief, ClaimRequest

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
    researcher = await db.get(Researcher, user.researcher_id) if user.researcher_id else None
    return MeResponse(
        email=user.email,
        is_admin=user.is_admin,
        researcher=ResearcherBrief.model_validate(researcher) if researcher else None,
    )


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _me(user, db)


@router.put("/me/researcher", response_model=MeResponse)
async def claim_researcher(
    body: ClaimRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Link the account to a Boğaziçi researcher profile. Not verified: any profile can be claimed."""
    if not await db.get(Researcher, body.researcher_id):
        raise HTTPException(status_code=404, detail="Researcher not found")
    user = await db.merge(user)
    user.researcher_id = body.researcher_id
    await db.commit()
    return await _me(user, db)


@router.delete("/me/researcher", response_model=MeResponse)
async def unclaim_researcher(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.merge(user)
    user.researcher_id = None
    await db.commit()
    return await _me(user, db)
