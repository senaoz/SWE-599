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

OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
OPENALEX_EMAIL: str | None = os.getenv("OPENALEX_EMAIL")

BOUN_OPENALEX_ID: str = "https://openalex.org/I4405392"
BOUN_CSV_PATH: str = os.getenv("BOUN_CSV_PATH", "research/data/cleaned/boun.csv")

# Embedding fallback (used when local Ollama is unavailable)
OLLAMA_CLOUD_API_KEY: str | None = os.getenv("OLLAMA_CLOUD_API_KEY")
OLLAMA_CLOUD_MODEL: str = os.getenv("OLLAMA_CLOUD_MODEL", "qwen3:embedding")

# RAG pipeline
RETRIEVE_MODEL: str = "qwen"                                           # Stage 1: qwen3-embedding via Ollama
RAG_RETRIEVE_TOP_K: int = int(os.getenv("RAG_RETRIEVE_TOP_K", "10"))  # Stage 1 → top-K researchers
RAG_LLM_TOP_K: int = int(os.getenv("RAG_LLM_TOP_K", "10"))           # Stage 2 → LLM rerank top-K
RAG_CONTEXT_PAPERS: int = int(os.getenv("RAG_CONTEXT_PAPERS", "5"))   # BOUN papers in LLM prompt
LLM_GENERATE_MODEL: str = os.getenv("LLM_GENERATE_MODEL", "llama3.2:3b")  # Stage 2 Ollama model
