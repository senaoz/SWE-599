from __future__ import annotations

from datetime import datetime, date
from pydantic import BaseModel, EmailStr


# ── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Institutions ──────────────────────────────────────────────────────────────

class InstitutionSearchResult(BaseModel):
    openalex_id: str
    display_name: str
    country_code: str | None = None

class FollowRequest(BaseModel):
    institution_openalex_id: str
    institution_name: str

class FollowedInstitution(BaseModel):
    institution_openalex_id: str
    institution_name: str
    followed_at: datetime

    class Config:
        from_attributes = True


# ── Papers ────────────────────────────────────────────────────────────────────

class MatchedBounPaper(BaseModel):
    title: str | None
    score: float

class ResearcherMatch(BaseModel):
    display_name: str
    score: float
    matched_papers: list[MatchedBounPaper] = []

class PaperOut(BaseModel):
    openalex_id: str
    title: str | None
    abstract: str | None
    publication_date: date | None
    source_institution_name: str | None
    top_researchers: list[ResearcherMatch]

class PapersResponse(BaseModel):
    papers: list[PaperOut]
    total: int
    page: int
    pages: int


# ── Researchers ───────────────────────────────────────────────────────────────

class ResearcherOut(BaseModel):
    id: str
    openalex_id: str
    display_name: str
    paper_count: int

    class Config:
        from_attributes = True

class ResearchersResponse(BaseModel):
    researchers: list[ResearcherOut]
    total: int
    page: int
    pages: int


# ── Admin ─────────────────────────────────────────────────────────────────────

class AdminStatus(BaseModel):
    paper_count: int
    match_count: int
    researcher_count: int
    last_run_at: datetime | None
