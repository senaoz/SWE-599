from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import (
    Boolean, Integer, String, Text, Float,
    DateTime, Date, ForeignKey, ForeignKeyConstraint, UniqueConstraint, Index,
    false, func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from backend.config import EMBEDDING_DIM
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    follows: Mapped[list[UserFollow]] = relationship("UserFollow", back_populates="user", cascade="all, delete-orphan")


class UserFavoriteResearcher(Base):
    """Boğaziçi researchers a user picked; they drive the For me feed."""
    __tablename__ = "user_favorite_researchers"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    researcher_id: Mapped[str] = mapped_column(String(50), ForeignKey("researchers.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserFollow(Base):
    __tablename__ = "user_follows"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    institution_openalex_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    institution_name: Mapped[str] = mapped_column(String(255), nullable=False)
    followed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship("User", back_populates="follows")


class FetchCursor(Base):
    __tablename__ = "fetch_cursors"

    institution_openalex_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_fetched_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserPaperView(Base):
    __tablename__ = "user_paper_views"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    paper_openalex_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FetchedPaper(Base):
    __tablename__ = "fetched_papers"

    openalex_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    doi: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    concepts_text: Mapped[str | None] = mapped_column(Text)  # dashboard filter only; not embedded (D7)
    type: Mapped[str | None] = mapped_column(String(50))     # OpenAlex work type (article, dataset, …)
    field: Mapped[str | None] = mapped_column(String(100))   # OpenAlex field of the primary topic
    oa_url: Mapped[str | None] = mapped_column(Text)
    publication_date: Mapped[date | None] = mapped_column(Date)
    source_institution_id: Mapped[str | None] = mapped_column(String(100))
    source_institution_name: Mapped[str | None] = mapped_column(String(255))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    embedding: Mapped[list | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_version: Mapped[str | None] = mapped_column(String(200))

    matches: Mapped[list[PaperResearcherMatch]] = relationship("PaperResearcherMatch", back_populates="paper", cascade="all, delete-orphan")


class Researcher(Base):
    __tablename__ = "researchers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    openalex_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    paper_count: Mapped[int] = mapped_column(Integer, default=0)

    matches: Mapped[list[PaperResearcherMatch]] = relationship("PaperResearcherMatch", back_populates="researcher")


class BounWork(Base):
    """One cleaned BOUN work (research/data/boun/boun_works.csv.gz), embedded once."""
    __tablename__ = "boun_works"

    openalex_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    doi: Mapped[str | None] = mapped_column(String(255))
    duplicate_ids: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False, server_default="{}")
    title: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)  # OpenAlex only; Crossref/S2 text is never stored (D5)
    abstract_source: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[str | None] = mapped_column(String(50))
    first_date: Mapped[date | None] = mapped_column(Date)
    n_authors: Mapped[int | None] = mapped_column(Integer)  # undercounts 100+-author works (only BOUN authors kept)
    large_collaboration: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())  # 100+ authors (D4)
    language_flag: Mapped[str | None] = mapped_column(String(20))
    primary_topic: Mapped[str | None] = mapped_column(String(255))  # OpenAlex topic, for researcher profiles
    embedding: Mapped[list | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_version: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (Index("idx_boun_works_doi", "doi"),)


class BounAuthorship(Base):
    __tablename__ = "boun_authorships"

    work_id: Mapped[str] = mapped_column(String(100), ForeignKey("boun_works.openalex_id", ondelete="CASCADE"), primary_key=True)
    researcher_id: Mapped[str] = mapped_column(String(50), ForeignKey("researchers.id", ondelete="CASCADE"), primary_key=True)

    __table_args__ = (Index("idx_boun_authorships_researcher", "researcher_id"),)


class PaperResearcherMatch(Base):
    __tablename__ = "paper_researcher_matches"

    paper_openalex_id: Mapped[str] = mapped_column(String(100), ForeignKey("fetched_papers.openalex_id", ondelete="CASCADE"), primary_key=True)
    researcher_id: Mapped[str] = mapped_column(String(50), ForeignKey("researchers.id", ondelete="CASCADE"), primary_key=True)
    embedding_version: Mapped[str] = mapped_column(String(200), primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    paper: Mapped[FetchedPaper] = relationship("FetchedPaper", back_populates="matches")
    researcher: Mapped[Researcher] = relationship("Researcher", back_populates="matches")

    __table_args__ = (
        Index("idx_matches_paper_version_rank", "paper_openalex_id", "embedding_version", "rank"),
        Index("idx_matches_researcher", "researcher_id"),
    )


class MatchEvidence(Base):
    """The BOUN works behind one match, shown under the researcher."""
    __tablename__ = "match_evidence"

    paper_openalex_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    researcher_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    embedding_version: Mapped[str] = mapped_column(String(200), primary_key=True)
    work_id: Mapped[str] = mapped_column(String(100), ForeignKey("boun_works.openalex_id", ondelete="CASCADE"), primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["paper_openalex_id", "researcher_id", "embedding_version"],
            ["paper_researcher_matches.paper_openalex_id", "paper_researcher_matches.researcher_id",
             "paper_researcher_matches.embedding_version"],
            ondelete="CASCADE",
        ),
    )


class PaperFeedback(Base):
    __tablename__ = "paper_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paper_openalex_id: Mapped[str] = mapped_column(String(100), ForeignKey("fetched_papers.openalex_id", ondelete="CASCADE"), nullable=False)
    researcher_id: Mapped[str] = mapped_column(String(50), ForeignKey("researchers.id", ondelete="CASCADE"), nullable=False)
    verdict: Mapped[str] = mapped_column(String(10), nullable=False)  # yes | partly | no
    reason: Mapped[str | None] = mapped_column(String(30))
    # What the user was shown when they rated it
    embedding_version: Mapped[str | None] = mapped_column(String(200))
    score: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "paper_openalex_id", "researcher_id"),)
