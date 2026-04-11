from __future__ import annotations

import logging
import os, sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

_RESEARCH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "research")
if _RESEARCH not in sys.path:
    sys.path.insert(0, _RESEARCH)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import auth, institutions, papers, admin, researchers


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # Seed researchers from boun.csv if table is empty
    from backend.services.seeder import seed_if_empty
    await seed_if_empty()

    # Start background scheduler
    from backend.scheduler import start_scheduler
    start_scheduler()

    yield

    from backend.scheduler import stop_scheduler
    stop_scheduler()


app = FastAPI(title="BOUN Paper Recommender", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(institutions.router)
app.include_router(papers.router)
app.include_router(admin.router)
app.include_router(researchers.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
