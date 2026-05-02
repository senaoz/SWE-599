from __future__ import annotations

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(engine.sync_engine, "connect")
def on_connect(dbapi_connection, connection_record):
    from pgvector.asyncpg import register_vector
    dbapi_connection.run_async(register_vector)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        await conn.run_sync(Base.metadata.create_all)

        # Migrate BYTEA embedding columns to vector(4096) (idempotent)
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='researcher_papers' AND column_name='embedding' AND data_type='bytea'
                ) THEN
                    ALTER TABLE researcher_papers DROP COLUMN embedding;
                    ALTER TABLE researcher_papers ADD COLUMN embedding vector(4096);
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='researchers' AND column_name='profile_embedding' AND data_type='bytea'
                ) THEN
                    ALTER TABLE researchers DROP COLUMN profile_embedding;
                    ALTER TABLE researchers ADD COLUMN profile_embedding vector(4096);
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='fetched_papers' AND column_name='embedding' AND data_type='bytea'
                ) THEN
                    ALTER TABLE fetched_papers DROP COLUMN embedding;
                    ALTER TABLE fetched_papers ADD COLUMN embedding vector(4096);
                END IF;
            END $$
        """))

        for stmt in [
            "ALTER TABLE paper_researcher_matches ADD COLUMN IF NOT EXISTS matched_paper_ids TEXT",
            "ALTER TABLE paper_researcher_matches ADD COLUMN IF NOT EXISTS llm_score FLOAT",
        ]:
            await conn.execute(text(stmt))

