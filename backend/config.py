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

DEFAULT_MODEL: str = "specter2"

# RAG pipeline
RETRIEVE_MODEL: str = "nomic"                                          # Stage 1: nomic-embed-text via Ollama
RAG_RETRIEVE_TOP_K: int = int(os.getenv("RAG_RETRIEVE_TOP_K", "20")) # Stage 1 → top-K researchers
RAG_LLM_TOP_K: int = int(os.getenv("RAG_LLM_TOP_K", "10"))          # Stage 2 → LLM rerank top-K
RAG_CONTEXT_PAPERS: int = int(os.getenv("RAG_CONTEXT_PAPERS", "3"))  # BOUN papers in LLM prompt
LLM_GENERATE_MODEL: str = os.getenv("LLM_GENERATE_MODEL", "llama3.2:3b")  # Stage 2 Ollama model

AVAILABLE_MODELS: list[dict] = [
    {"key": "specter2",      "label": "SPECTER2",           "description": "allenai/specter2_base — best for scientific papers", "requires_ollama": False},
    {"key": "minilm",        "label": "MiniLM",             "description": "all-MiniLM-L6-v2 — fast general-purpose embeddings", "requires_ollama": False},
    {"key": "bm25",          "label": "BM25",               "description": "Probabilistic keyword ranking, no GPU needed",        "requires_ollama": False},
    {"key": "tfidf",         "label": "TF-IDF",             "description": "TF-IDF cosine similarity, fastest CPU method",         "requires_ollama": False},
    {"key": "llama",         "label": "Llama 3.2",          "description": "Llama 3.2 3B reranker via Ollama",                    "requires_ollama": True},
    {"key": "embeddinggemma","label": "Embedding Gemma",    "description": "Gemma embedding model via Ollama",                    "requires_ollama": True},
    {"key": "llama+minilm",  "label": "Llama + MiniLM",    "description": "Combined Llama + MiniLM embeddings",                  "requires_ollama": True},
    {"key": "qwen",          "label": "Qwen3",              "description": "Qwen3 embedding via Ollama",                          "requires_ollama": True},
    {"key": "qwen+minilm",   "label": "Qwen + MiniLM",     "description": "Combined Qwen + MiniLM embeddings",                   "requires_ollama": True},
]
