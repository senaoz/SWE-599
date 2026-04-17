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
    researcher_id: str
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
    is_seen: bool = False

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


# ── Paper Detail ─────────────────────────────────────────────────────────────

class PaperDetailOut(BaseModel):
    openalex_id: str
    title: str | None
    abstract: str | None
    publication_date: date | None
    source_institution_name: str | None
    all_researchers: list[ResearcherMatch]


# ── Researcher Detail ─────────────────────────────────────────────────────────

class MatchedPaperForResearcher(BaseModel):
    openalex_id: str
    title: str | None
    publication_date: date | None
    source_institution_name: str | None
    score: float

class ResearcherDetailOut(BaseModel):
    id: str
    openalex_id: str
    display_name: str
    paper_count: int
    matched_papers: list[MatchedPaperForResearcher]
    total_matches: int
    page: int
    pages: int

    class Config:
        from_attributes = True


class ResearcherMergedOut(BaseModel):
    display_name: str
    ids: list[str]
    openalex_urls: list[str]
    total_papers: int
    matched_papers: list[MatchedPaperForResearcher]
    total_matches: int


# ── Feedback ──────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    paper_openalex_id: str
    researcher_id: str
    is_relevant: bool


# ── Admin ─────────────────────────────────────────────────────────────────────

class AdminStatus(BaseModel):
    paper_count: int
    match_count: int
    researcher_count: int
    last_run_at: datetime | None
