from __future__ import annotations

import numpy as np
import requests

from backend.config import EMBED_URL, EMBED_MODEL, EMBEDDING_DIM


def paper_text(title: str | None, abstract: str | None) -> str:
    """The embedded text, the same for BOUN works and new papers (D7): title + abstract, untruncated.
    Must stay identical to src.boun_data.work_texts, or the research vectors stop matching."""
    return f"{title or ''} {abstract or ''}".strip()


def encode(texts: list[str], batch_size: int = 32, timeout: float = 600) -> np.ndarray:
    """Embed texts with the llama-server encoder (OpenAI-style /embeddings). Returns (n, dim) float32."""
    out: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        resp = requests.post(
            f"{EMBED_URL.rstrip('/')}/embeddings",
            json={"model": EMBED_MODEL, "input": texts[start:start + batch_size]},
            timeout=timeout,
        )
        resp.raise_for_status()
        rows = sorted(resp.json()["data"], key=lambda d: d["index"])
        out.extend(r["embedding"] for r in rows)
    embs = np.asarray(out, dtype=np.float32)
    if embs.shape != (len(texts), EMBEDDING_DIM):
        raise ValueError(f"Encoder returned shape {embs.shape}, expected ({len(texts)}, {EMBEDDING_DIM}).")
    return embs


def emb_to_list(emb: np.ndarray) -> list:
    """Convert embedding array to list for pgvector storage."""
    return emb.astype(np.float32).tolist()


def row_to_emb(vec) -> np.ndarray:
    """Convert pgvector column value (list, array or pgvector.Vector) to numpy array."""
    if hasattr(vec, "to_numpy"):
        vec = vec.to_numpy()
    return np.array(vec, dtype=np.float32)
