from __future__ import annotations

import os
import sys
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.similarity import MODEL_MAP, OLLAMA_MODEL_MAP, MAX_TEXT_CHARS

_model_cache: dict[str, any] = {}


def _get_st_model(model_name: str):
    """Load and cache a SentenceTransformer model."""
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer
        import torch
        device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        _model_cache[model_name] = SentenceTransformer(model_name, device=device)
    return _model_cache[model_name]


def _truncate(texts: list[str], model_key: str) -> list[str]:
    limit = MAX_TEXT_CHARS.get(model_key, 1024)
    return [t[:limit] if t else "" for t in texts]


def encode_texts(texts: list[str], model_key: str) -> np.ndarray:
    """Encode texts with the given model key. Returns (n, dim) float32 array."""
    model_id = MODEL_MAP.get(model_key)
    if not model_id:
        raise ValueError(f"Unknown embedding model: {model_key}")
    model = _get_st_model(model_id)
    truncated = _truncate(texts, model_key)
    return model.encode(truncated, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)


def encode_texts_ollama(texts: list[str], model_key: str, ollama_url: str) -> np.ndarray:
    """Encode texts via Ollama. Returns (n, dim) float32 array."""
    import requests
    ollama_model = OLLAMA_MODEL_MAP.get(model_key)
    if not ollama_model:
        raise ValueError(f"Unknown Ollama model: {model_key}")

    embeddings = []
    for text in texts:
        resp = requests.post(
            f"{ollama_url}/api/embed",
            json={"model": ollama_model, "input": text[:2048]},
            timeout=60,
        )
        resp.raise_for_status()
        embeddings.append(resp.json()["embeddings"][0])
    return np.array(embeddings, dtype=np.float32)


def batch_score(paper_embs: np.ndarray, researcher_embs: np.ndarray) -> np.ndarray:
    """Cosine similarity matrix: (n_papers, n_researchers)."""
    return cosine_similarity(paper_embs, researcher_embs).astype(np.float32)


def emb_to_bytes(emb: np.ndarray) -> bytes:
    return emb.astype(np.float32).tobytes()


def bytes_to_emb(blob: bytes, dim: int = 768) -> np.ndarray:
    arr = np.frombuffer(blob, dtype=np.float32)
    return arr.reshape(1, -1) if arr.ndim == 1 else arr
