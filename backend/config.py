from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://swe599:swe599@localhost:5432/swe599",
)

JWT_SECRET: str = os.getenv("JWT_SECRET", "change-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

MATCH_THRESHOLD: float = float(os.getenv("MATCH_THRESHOLD", "0.3"))
TOP_K_MATCHES: int = int(os.getenv("TOP_K_MATCHES", "5"))
JOB_INTERVAL_HOURS: int = int(os.getenv("JOB_INTERVAL_HOURS", "6"))

OPENALEX_EMAIL: str | None = os.getenv("OPENALEX_EMAIL")

BOUN_OPENALEX_ID: str = "https://openalex.org/I4405392"
# Research folder: the cleaned BOUN data in data/boun (research/audit/BOUN_DATA.md), the gitignored
# Crossref/S2 abstract cache and the Experiment B vectors (EMBEDDING_CACHE_PATH, reused when the text matches)
RESEARCH_DIR: str = os.getenv("RESEARCH_DIR", "research")
EMBEDDING_CACHE_PATH: str = os.getenv("EMBEDDING_CACHE_PATH", os.path.join(RESEARCH_DIR, "data/v2/embeddings_boun/qwen.npz"))

# Encoder: llama-server with Qwen3-Embedding-8B (docs/MATCHING_DESIGN.md, D1, D2, D7)
EMBED_URL: str = os.getenv("EMBED_URL", "http://localhost:1337/v1")  # OpenAI-style base URL
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "Qwen/Qwen3-Embedding-8B-Q4_K_M")  # id under /v1/models
EMBEDDING_DIM: int = 4096
# Everything that makes two vectors incomparable; change it and the BOUN index is re-embedded.
EMBEDDING_VERSION: str = os.getenv(
    "EMBEDDING_VERSION", "qwen3-emb-8b|llama.cpp-b11146-q4_k_m|d4096|last|ta_full|noinstr"
)

# Matching
MATCH_AGGREGATION: str = os.getenv("MATCH_AGGREGATION", "max")         # max | mean_top3 (services/ranking.py)
RETRIEVE_WORKS: int = int(os.getenv("RETRIEVE_WORKS", "50"))          # BOUN works retrieved per new paper
RAG_RETRIEVE_TOP_K: int = int(os.getenv("RAG_RETRIEVE_TOP_K", "10"))  # researchers stored per paper
RAG_CONTEXT_PAPERS: int = int(os.getenv("RAG_CONTEXT_PAPERS", "5"))   # matched BOUN works stored per researcher
