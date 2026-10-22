"""Schema, seeder, matching job and read path against a real Postgres with pgvector.

Run with TEST_DATABASE_URL pointing at a throwaway database (every test drops its schema), e.g.
    docker run -d --rm -p 5433:5432 -e POSTGRES_PASSWORD=t pgvector/pgvector:pg16
    TEST_DATABASE_URL=postgresql+asyncpg://postgres:t@localhost:5433/postgres pytest backend/tests
"""
import asyncio
import hashlib
import json
import os
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")

DIM = 4096


def unit(i: int) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    v[i] = 1.0
    return v


def mix(*parts: tuple[int, float]) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    for i, w in parts:
        v[i] = w
    return v / np.linalg.norm(v)


def run(coro_fn):
    """Run one test body on a clean schema, in its own event loop."""
    from sqlalchemy import text
    from backend.database import engine

    async def body():
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        try:
            await coro_fn()
        finally:
            await engine.dispose()

    asyncio.run(body())


# Five works: w1–w4 have BOUN authors, w5 has none. w3's text is not in the cache.
WORKS = [
    # id, doi, duplicate_ids, title, abstract, authors
    ("https://openalex.org/W1", "10.1/one", [], "Graph neural networks", "Message passing.", ["A1"]),
    ("https://openalex.org/W2", "10.1/two", ["https://openalex.org/W2pre"], "Protein folding", "Structures.", ["A2"]),
    ("https://openalex.org/W3", "", [], "Turkish poetry", "", ["A3"]),
    ("https://openalex.org/W4", "10.1/four", [], "Graph theory", "Colouring.", ["A1", "A2"]),
    ("https://openalex.org/W5", "10.1/five", [], "Orphan work", "No BOUN author id.", []),
]
VECTORS = {"https://openalex.org/W1": unit(0), "https://openalex.org/W2": unit(1),
           "https://openalex.org/W3": unit(2), "https://openalex.org/W4": mix((0, 0.6), (3, 0.8)),
           "https://openalex.org/W5": unit(4)}


@pytest.fixture
def research_dir(tmp_path, monkeypatch):
    """A research folder with the cleaned-data files and a cache holding all vectors but W3's."""
    boun = tmp_path / "data" / "boun"
    boun.mkdir(parents=True)
    a = lambda r: f"https://openalex.org/{r}"
    pd.DataFrame([{
        "id": wid, "doi": doi, "duplicate_ids": json.dumps(dups), "title": title, "abstract": abstract,
        "abstract_source": "openalex" if abstract else "none", "type": "article", "first_date": "2024-01-01",
        "author_ids": json.dumps([a(x) for x in authors]), "large_collaboration": False, "language_flag": "en",
        "primary_topic": "Graph theory" if "Graph" in title else "Proteins",
    } for wid, doi, dups, title, abstract, authors in WORKS]).to_csv(boun / "boun_works.csv.gz", index=False)
    pd.DataFrame([{"researcher_id": a(r), "display_name": f"Researcher {r}", "n_works": n}
                  for r, n in (("A1", 2), ("A2", 2), ("A3", 1))]).to_csv(boun / "researchers.csv.gz", index=False)
    pd.DataFrame([{"researcher_id": a(r), "work_id": wid} for wid, *_, authors in WORKS for r in authors]
                 ).to_csv(boun / "researcher_works.csv.gz", index=False)

    from src.boun_data import work_texts
    texts = work_texts(str(tmp_path))
    cache = tmp_path / "cache.npz"
    np.savez(cache, **{hashlib.sha256(t.encode()).hexdigest(): VECTORS[wid]
                       for wid, t in texts.items() if wid != "https://openalex.org/W3"})

    from backend.services import seeder
    monkeypatch.setattr(seeder, "RESEARCH_DIR", str(tmp_path))
    monkeypatch.setattr(seeder, "EMBEDDING_CACHE_PATH", str(cache))
    return tmp_path


@pytest.fixture
def stub_encoder(monkeypatch):
    """Encoder stub: returns the vector registered for a text and records what it was asked."""
    from backend.services import embedding
    calls, by_text = [], {}

    def encode(texts, **_):
        calls.extend(texts)
        return np.vstack([by_text[t] for t in texts])

    monkeypatch.setattr(embedding, "encode", encode)
    return SimpleNamespace(calls=calls, by_text=by_text)


async def seed(stub_encoder):
    from backend.database import init_db
    from backend.services.seeder import _load_boun_data, embed_missing_works
    stub_encoder.by_text["Turkish poetry"] = VECTORS["https://openalex.org/W3"]
    await init_db()
    await _load_boun_data()
    await embed_missing_works()


def test_init_db_creates_schema_and_is_idempotent():
    from sqlalchemy import text
    from backend.database import engine, init_db

    async def body():
        await init_db()
        await init_db()
        async with engine.connect() as conn:
            tables = set(await conn.scalars(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")))
        assert {"boun_works", "boun_authorships", "match_evidence", "paper_researcher_matches"} <= tables
        assert "researcher_papers" not in tables
    run(body)


def test_init_db_refuses_old_schema_and_wrong_dimension():
    from sqlalchemy import text
    from backend.database import engine, init_db, SchemaError

    async def old_schema():
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE researcher_papers (id int)"))
        with pytest.raises(SchemaError, match="old schema"):
            await init_db()
    run(old_schema)

    async def wrong_dim():
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE TABLE boun_works (openalex_id varchar(100) PRIMARY KEY, embedding vector(3))"))
        with pytest.raises(SchemaError, match="vector\\(4096\\)"):
            await init_db()
    run(wrong_dim)


def test_seeder_loads_data_and_reuses_cached_vectors(research_dir, stub_encoder):
    from sqlalchemy import select, func
    from backend.config import EMBEDDING_VERSION
    from backend.database import SessionLocal
    from backend.models import BounWork, BounAuthorship, Researcher

    async def body():
        await seed(stub_encoder)
        async with SessionLocal() as db:
            assert await db.scalar(select(func.count(Researcher.id))) == 3
            assert await db.scalar(select(func.count()).select_from(BounAuthorship)) == 5
            works = {w.openalex_id: w for w in await db.scalars(select(BounWork))}
        assert len(works) == 5
        assert all(w.embedding_version == EMBEDDING_VERSION for w in works.values())
        assert works["https://openalex.org/W2"].duplicate_ids == ["https://openalex.org/W2pre"]
        assert works["https://openalex.org/W1"].doi == "10.1/one"
        assert np.allclose(works["https://openalex.org/W4"].embedding, VECTORS["https://openalex.org/W4"])
        # Only the work missing from the cache went to the encoder.
        assert stub_encoder.calls == ["Turkish poetry"]
    run(body)


def test_matching_ranks_researchers_and_excludes_the_paper_itself(research_dir, stub_encoder):
    from sqlalchemy import select
    from backend.database import SessionLocal
    from backend.models import FetchedPaper, PaperResearcherMatch, MatchEvidence
    from backend.services.matching import _match_and_store

    papers = [
        {"openalex_id": "https://openalex.org/P1", "doi": None},               # about graphs
        {"openalex_id": "https://openalex.org/W1", "doi": None},               # W1 itself arrives
        {"openalex_id": "https://openalex.org/P3", "doi": "https://doi.org/10.1/TWO"},  # W2 by DOI
        {"openalex_id": "https://openalex.org/W2pre", "doi": None},            # W2's merged preprint
        {"openalex_id": "https://openalex.org/P5", "doi": None},               # off-topic
    ]
    embs = np.vstack([mix((0, 0.9), (3, 0.3)), unit(0), unit(1), unit(1), unit(9)])

    async def body():
        await seed(stub_encoder)
        async with SessionLocal() as db:
            db.add_all([FetchedPaper(openalex_id=p["openalex_id"]) for p in papers])
            await db.commit()
        assert await _match_and_store(papers, embs, "TEST") > 0

        async with SessionLocal() as db:
            matches = {}
            for m in await db.scalars(select(PaperResearcherMatch).order_by(PaperResearcherMatch.rank)):
                matches.setdefault(m.paper_openalex_id, []).append(m)
            evidence = {(e.paper_openalex_id, e.researcher_id): e.work_id
                        for e in await db.scalars(select(MatchEvidence).order_by(MatchEvidence.score))}

        p1 = matches["https://openalex.org/P1"]
        assert [m.researcher_id for m in p1][:2] == ["A1", "A2"] and [m.rank for m in p1][:2] == [1, 2]
        assert evidence[("https://openalex.org/P1", "A2")] == "https://openalex.org/W4"
        # W1 itself is excluded, so A1 is found only through W4 (cosine 0.6).
        assert matches["https://openalex.org/W1"][0].score == pytest.approx(0.6, abs=1e-3)
        # W2 is excluded by DOI and by duplicate id, so A2's best is W4 (cosine 0), below the floor.
        assert "https://openalex.org/P3" not in matches
        assert "https://openalex.org/W2pre" not in matches
        # Off-topic paper: best cosine 0, below the floor.
        assert "https://openalex.org/P5" not in matches

        # Rerunning replaces the matches instead of duplicating them.
        await _match_and_store(papers[:1], embs[:1], "TEST")
        async with SessionLocal() as db:
            again = list(await db.scalars(select(PaperResearcherMatch).where(
                PaperResearcherMatch.paper_openalex_id == "https://openalex.org/P1")))
        assert len(again) == len(p1)
    run(body)


async def matched_paper_and_user(stub_encoder, pid="https://openalex.org/P1", **paper):
    """Seed, add one new graph paper matched to A1 (rank 1) and A2 (rank 2), and one user."""
    from backend.database import SessionLocal
    from backend.models import FetchedPaper, User
    from backend.services.matching import _match_and_store

    await seed(stub_encoder)
    async with SessionLocal() as db:
        db.add(FetchedPaper(openalex_id=pid, title="New graph paper", **paper))
        user = User(email="u@example.com", password_hash="x")
        db.add(user)
        await db.commit()
        user_id = user.id
    await _match_and_store([{"openalex_id": pid, "doi": None}], mix((0, 0.9), (3, 0.3))[None, :], "TEST")
    return user_id


def test_read_path_and_feedback_snapshot(research_dir, stub_encoder):
    from backend.config import EMBEDDING_VERSION
    from backend.database import SessionLocal
    from backend.models import PaperFeedback, User
    from backend.routers.feedback import submit_feedback
    from backend.routers.papers import load_matches
    from backend.schemas import FeedbackRequest
    from sqlalchemy import select

    pid = "https://openalex.org/P1"

    async def body():
        user_id = await matched_paper_and_user(stub_encoder)
        async with SessionLocal() as db:
            rows = await load_matches(db, [pid], user_id)
            assert [m.researcher_id for m in rows][:2] == ["A1", "A2"]
            assert rows[0].display_name == "Researcher A1"
            assert [p.title for p in rows[0].matched_papers] == ["Graph neural networks", "Graph theory"]
            assert rows[0].matched_papers[0].work_id == "https://openalex.org/W1"
            assert rows[0].matched_papers[0].year == 2024
            assert rows[0].my_verdict is None

            user = await db.get(User, user_id)
            await submit_feedback(FeedbackRequest(
                paper_openalex_id=pid, researcher_id="A2", verdict="partly", reason="too_general"), user, db)
            fb = await db.scalar(select(PaperFeedback))
            assert (fb.verdict, fb.reason, fb.embedding_version, fb.rank) == ("partly", "too_general", EMBEDDING_VERSION, 2)
            assert fb.score == pytest.approx(rows[1].score)
            assert (await load_matches(db, [pid], user_id))[1].my_verdict == "partly"

            # "yes" drops the reason; None withdraws the answer.
            await submit_feedback(FeedbackRequest(
                paper_openalex_id=pid, researcher_id="A2", verdict="yes", reason="too_general"), user, db)
            assert (await db.scalar(select(PaperFeedback.reason))) is None
            await submit_feedback(FeedbackRequest(paper_openalex_id=pid, researcher_id="A2", verdict=None), user, db)
            assert await db.scalar(select(PaperFeedback)) is None
    run(body)


def test_claim_and_for_me_feed(research_dir, stub_encoder):
    from fastapi import HTTPException
    from backend.database import SessionLocal
    from backend.models import User
    from backend.routers.auth import claim_researcher, unclaim_researcher
    from backend.routers.papers import get_papers_for_me
    from backend.schemas import ClaimRequest

    async def body():
        user_id = await matched_paper_and_user(stub_encoder)
        async with SessionLocal() as db:
            user = await db.get(User, user_id)
            with pytest.raises(HTTPException) as e:
                await get_papers_for_me(page=1, limit=20, from_date=None, to_date=None, search=None, field=None,
                                        current_user=user, db=db)
            assert e.value.status_code == 409

            me = await claim_researcher(ClaimRequest(researcher_id="A2"), user, db)
            assert me.researcher.id == "A2" and me.researcher.display_name == "Researcher A2"
            feed = await get_papers_for_me(page=1, limit=20, from_date=None, to_date=None, search=None, field=None,
                                           current_user=user, db=db)
            assert [p.openalex_id for p in feed.papers] == ["https://openalex.org/P1"]
            assert feed.papers[0].my_match.researcher_id == "A2" and feed.papers[0].my_match.rank == 2

            await claim_researcher(ClaimRequest(researcher_id="A3"), user, db)
            feed = await get_papers_for_me(page=1, limit=20, from_date=None, to_date=None, search=None, field=None,
                                           current_user=user, db=db)
            assert feed.total == 0  # A3 is stored at rank 3 with cosine 0, below the 0.3 shown in Explore

            with pytest.raises(HTTPException):
                await claim_researcher(ClaimRequest(researcher_id="NOPE"), user, db)
            assert (await unclaim_researcher(user, db)).researcher is None
    run(body)


def test_explore_field_filter_and_fields(research_dir, stub_encoder):
    from backend.database import SessionLocal
    from backend.models import FetchedPaper, User, UserFollow
    from backend.routers.papers import get_papers, get_fields

    inst = "https://openalex.org/I1"

    async def body():
        user_id = await matched_paper_and_user(stub_encoder, source_institution_id=inst, field="Mathematics",
                                               type="article", doi="10.9/p1")
        async with SessionLocal() as db:
            db.add(FetchedPaper(openalex_id="https://openalex.org/P2", title="Other", source_institution_id=inst,
                                field="Medicine", type="dataset"))
            db.add(UserFollow(user_id=user_id, institution_openalex_id=inst, institution_name="Inst"))
            await db.commit()
            user = await db.get(User, user_id)
            assert [(f.field, f.count) for f in await get_fields(user, db)] in (
                [("Mathematics", 1), ("Medicine", 1)], [("Medicine", 1), ("Mathematics", 1)])

            kwargs = dict(page=1, limit=20, institution_id=None, from_date=None, to_date=None, min_score=0.3,
                          include_unmatched=True, search=None, concept=None, current_user=user, db=db)
            assert (await get_papers(field=None, **kwargs)).total == 2
            only = await get_papers(field="Mathematics", **kwargs)
            assert [p.openalex_id for p in only.papers] == ["https://openalex.org/P1"]
            assert (only.papers[0].type, only.papers[0].doi) == ("article", "10.9/p1")
            assert only.papers[0].top_researchers[0].researcher_id == "A1"
    run(body)


def test_researcher_profile_and_admin_feedback(research_dir, stub_encoder):
    from backend.database import SessionLocal
    from backend.models import User
    from backend.routers.admin import feedback_summary
    from backend.routers.feedback import submit_feedback
    from backend.routers.researchers import researcher_profile
    from backend.schemas import FeedbackRequest

    pid = "https://openalex.org/P1"

    async def body():
        user_id = await matched_paper_and_user(stub_encoder)
        async with SessionLocal() as db:
            profile = await researcher_profile(db, ["A1"])
            assert profile.topics == ["Graph theory"]
            assert {w.title for w in profile.recent_works} == {"Graph neural networks", "Graph theory"}
            assert [(c.id, c.shared_works) for c in profile.coauthors] == [("A2", 1)]  # through W4

            user = await db.get(User, user_id)
            await submit_feedback(FeedbackRequest(paper_openalex_id=pid, researcher_id="A1", verdict="yes"), user, db)
            await submit_feedback(FeedbackRequest(
                paper_openalex_id=pid, researcher_id="A2", verdict="no", reason="different_field"), user, db)
            summary = await feedback_summary(user, db)
            assert summary.total == 2
            assert [(r.rank, r.yes, r.no) for r in summary.by_rank] == [(1, 1, 0), (2, 0, 1)]
            assert summary.reasons == {"different_field": 1}
    run(body)


def test_init_db_refuses_a_schema_with_missing_columns():
    from sqlalchemy import text
    from backend.database import engine, init_db, SchemaError

    async def body():
        await init_db()
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE users DROP COLUMN researcher_id"))
        with pytest.raises(SchemaError, match="users.researcher_id"):
            await init_db()
    run(body)
