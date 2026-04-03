from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import (
    Integer, String, Text, Float, LargeBinary,
    DateTime, Date, ForeignKey, UniqueConstraint, Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    follows: Mapped[list[UserFollow]] = relationship("UserFollow", back_populates="user", cascade="all, delete-orphan")


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


class FetchedPaper(Base):
    __tablename__ = "fetched_papers"

    openalex_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    concepts_text: Mapped[str | None] = mapped_column(Text)
    publication_date: Mapped[date | None] = mapped_column(Date)
    source_institution_id: Mapped[str | None] = mapped_column(String(100))
    source_institution_name: Mapped[str | None] = mapped_column(String(255))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)

    matches: Mapped[list[PaperResearcherMatch]] = relationship("PaperResearcherMatch", back_populates="paper", cascade="all, delete-orphan")


class Researcher(Base):
    __tablename__ = "researchers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    openalex_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    paper_count: Mapped[int] = mapped_column(Integer, default=0)
    profile_embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    profile_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    papers: Mapped[list[ResearcherPaper]] = relationship("ResearcherPaper", back_populates="researcher", cascade="all, delete-orphan")
    matches: Mapped[list[PaperResearcherMatch]] = relationship("PaperResearcherMatch", back_populates="researcher")


class ResearcherPaper(Base):
    __tablename__ = "researcher_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    researcher_id: Mapped[str] = mapped_column(String(50), ForeignKey("researchers.id"), nullable=False)
    paper_openalex_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    concepts_text: Mapped[str | None] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(Integer)

    researcher: Mapped[Researcher] = relationship("Researcher", back_populates="papers")

    __table_args__ = (UniqueConstraint("researcher_id", "paper_openalex_id"),)


class PaperResearcherMatch(Base):
    __tablename__ = "paper_researcher_matches"

    paper_openalex_id: Mapped[str] = mapped_column(String(100), ForeignKey("fetched_papers.openalex_id"), primary_key=True)
    researcher_id: Mapped[str] = mapped_column(String(50), ForeignKey("researchers.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False, default="specter2")

    paper: Mapped[FetchedPaper] = relationship("FetchedPaper", back_populates="matches")
    researcher: Mapped[Researcher] = relationship("Researcher", back_populates="matches")

    __table_args__ = (
        Index("idx_matches_paper_score", "paper_openalex_id", "score"),
    )


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
