from __future__ import annotations

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(engine.sync_engine, "connect")
def on_connect(dbapi_connection, connection_record):
    # No asyncpg vector codec: it rejects the text that pgvector's SQLAlchemy type binds.
    async def setup(conn):
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    dbapi_connection.run_async(setup)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with SessionLocal() as session:
        yield session


class SchemaError(RuntimeError):
    pass


async def init_db() -> None:
    """Create the schema. There is no migration tool yet (docs/MATCHING_DESIGN.md, D9): a database
    from the old schema, or with a wrong embedding dimension, stops start-up instead of losing data."""
    from backend.config import EMBEDDING_DIM
    import backend.models  # noqa: F401  (registers the tables on Base.metadata)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        if await conn.scalar(text("SELECT to_regclass('public.researcher_papers') IS NOT NULL")):
            raise SchemaError(
                "This database has the old schema (researcher_papers). Reset it "
                "(e.g. `docker compose down -v`) and start again."
            )

        await conn.run_sync(Base.metadata.create_all)

        rows = await conn.execute(text("""
            SELECT c.relname, format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
            WHERE a.attname = 'embedding' AND c.relkind = 'r' AND NOT a.attisdropped
              AND c.relnamespace = 'public'::regnamespace
        """))
        wrong = {table: type_ for table, type_ in rows if type_ != f"vector({EMBEDDING_DIM})"}
        if wrong:
            raise SchemaError(f"Embedding columns are not vector({EMBEDDING_DIM}): {wrong}")

        # create_all never alters an existing table, so a database from an older version of the
        # schema would fail later on a missing column.
        rows = await conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
        ))
        present = {(t, c) for t, c in rows}
        missing = sorted(
            f"{table.name}.{column.name}"
            for table in Base.metadata.sorted_tables for column in table.columns
            if (table.name, column.name) not in present
        )
        if missing:
            raise SchemaError(
                f"The database schema is older than the code (missing {', '.join(missing)}). "
                "Reset it (e.g. `docker compose down -v`) and start again."
            )
