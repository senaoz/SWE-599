from __future__ import annotations

from datetime import datetime, date
from typing import Literal

from pydantic import BaseModel, EmailStr

Verdict = Literal["yes", "partly", "no"]
VerdictReason = Literal["different_field", "too_general", "collaboration_only", "same_author"]


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


class ResearcherBrief(BaseModel):
    id: str
    openalex_id: str
    display_name: str
    paper_count: int

    class Config:
        from_attributes = True


class MeResponse(BaseModel):
    email: str
    is_admin: bool
    researcher: ResearcherBrief | None = None


class ClaimRequest(BaseModel):
    researcher_id: str


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
    work_id: str
    title: str | None
    score: float
    year: int | None = None
    large_collaboration: bool = False

class ResearcherMatch(BaseModel):
    paper_openalex_id: str
    researcher_id: str
    display_name: str
    score: float
    rank: int
    matched_papers: list[MatchedBounPaper] = []
    my_verdict: Verdict | None = None

class PaperOut(BaseModel):
    openalex_id: str
    title: str | None
    abstract: str | None
    publication_date: date | None
    source_institution_name: str | None
    doi: str | None = None
    type: str | None = None
    field: str | None = None
    oa_url: str | None = None
    top_researchers: list[ResearcherMatch]
    my_match: ResearcherMatch | None = None  # the user's own researcher, in For me
    is_seen: bool = False

class FieldCount(BaseModel):
    field: str
    count: int

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
    doi: str | None = None
    type: str | None = None
    field: str | None = None
    oa_url: str | None = None
    all_researchers: list[ResearcherMatch]


# ── Researcher Detail ─────────────────────────────────────────────────────────

class MatchedPaperForResearcher(BaseModel):
    openalex_id: str
    title: str | None
    publication_date: date | None
    source_institution_name: str | None
    score: float

class RecentWork(BaseModel):
    work_id: str
    title: str | None
    year: int | None

class Coauthor(BaseModel):
    id: str
    display_name: str
    shared_works: int

class ResearcherProfile(BaseModel):
    topics: list[str] = []
    recent_works: list[RecentWork] = []
    coauthors: list[Coauthor] = []

class ResearcherDetailOut(ResearcherProfile):
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


class ResearcherMergedOut(ResearcherProfile):
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
    verdict: Verdict | None  # None withdraws the answer
    reason: VerdictReason | None = None


# ── Admin ─────────────────────────────────────────────────────────────────────

class AdminStatus(BaseModel):
    paper_count: int
    match_count: int
    researcher_count: int
    unmatched_count: int
    last_run_at: datetime | None
    embedding_version: str


class FeedbackByRank(BaseModel):
    rank: int
    yes: int = 0
    partly: int = 0
    no: int = 0


class FeedbackSummary(BaseModel):
    embedding_version: str
    total: int
    by_rank: list[FeedbackByRank]
    reasons: dict[str, int]
