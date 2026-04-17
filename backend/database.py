from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Migrate existing tables to add new columns (idempotent)
        from sqlalchemy import text
        for stmt in [
            "ALTER TABLE researcher_papers ADD COLUMN IF NOT EXISTS embedding BYTEA",
            "ALTER TABLE paper_researcher_matches ADD COLUMN IF NOT EXISTS matched_paper_ids TEXT",
            "ALTER TABLE paper_researcher_matches ADD COLUMN IF NOT EXISTS llm_score FLOAT",
        ]:
            await conn.execute(text(stmt))

