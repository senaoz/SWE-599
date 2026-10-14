"""Phase 5 candidate expansion over a graph (research/audit/PHASE5_DESIGN.md, tasks 5.6–5.7).

GRIT-style: keep the first-stage list's length K, take its top t as seeds, and replace
its bottom fraction b with the graph neighbours of the seeds that are not already kept.
The graph is either the leakage-controlled co-citation graph (src/cograph.py), its
degree-preserving random rewiring, or a document kNN graph from the embeddings.

LADR-style (adaptive): start from lexical seeds, score them and their kNN neighbours
with the dense model, and keep exploring the neighbours of the current top results
until the top list stops changing. It approximates exhaustive dense retrieval while
scoring only part of the corpus.
"""
from __future__ import annotations

import numpy as np


def cocitation_scores(g, seeds, mask: np.ndarray, norm: str = "count") -> np.ndarray:
    """Co-citation of every doc with the seeds over allowed citers.

    norm='count': number of (allowed citer, seed) pairs; 'cosine': divided by
    sqrt(allowed degree of the doc), so very popular works do not dominate.
    """
    s = g.cocitation(list(seeds), mask)
    if norm == "cosine":
        deg = g.degree(mask)
        s = np.divide(s, np.sqrt(deg), out=np.zeros_like(s), where=deg > 0)
    return s


def knn_scores(knn: np.ndarray, knn_sim: np.ndarray, seeds, n_docs: int) -> np.ndarray:
    """Sum of similarities from the seeds to their kNN neighbours."""
    s = np.zeros(n_docs)
    np.add.at(s, knn[list(seeds)].ravel(), knn_sim[list(seeds)].ravel())
    return s


def grit_expand(top: np.ndarray, t: int, b: float, graph_scores: np.ndarray,
                cand_mask: np.ndarray, tie: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Replace the bottom fraction b of `top` with the best graph neighbours of its top t.

    Neighbours must be candidates with a positive graph score that are not in the kept
    head; they are ordered by graph score, then by `tie` (the first-stage score). If there
    are fewer neighbours than free slots, the original bottom fills the rest in order.
    Returns (new list of the same length, the added doc indices).
    """
    K = len(top)
    r = int(round(K * b))
    keep = top[:K - r]
    ok = cand_mask & (graph_scores > 0)
    ok[keep] = False
    nb = np.flatnonzero(ok)
    nb = nb[np.lexsort((-tie[nb], -graph_scores[nb]))][:r]
    fill = [i for i in top[K - r:] if i not in set(nb.tolist())][:r - len(nb)]
    return np.concatenate([keep, nb, np.asarray(fill, dtype=keep.dtype)]), nb


def knn_graph(emb: np.ndarray, k: int, chunk: int = 2048) -> tuple[np.ndarray, np.ndarray]:
    """k nearest neighbours (cosine, excluding self) of every row: (indices, similarities)."""
    x = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    idx = np.empty((len(x), k), dtype=np.int64)
    sim = np.empty((len(x), k), dtype=np.float32)
    for start in range(0, len(x), chunk):
        s = x[start:start + chunk] @ x.T
        rows = np.arange(s.shape[0])
        s[rows, rows + start] = -np.inf
        part = np.argpartition(-s, k, axis=1)[:, :k]
        ps = np.take_along_axis(s, part, axis=1)
        o = np.argsort(-ps, axis=1)
        idx[start:start + chunk] = np.take_along_axis(part, o, axis=1)
        sim[start:start + chunk] = np.take_along_axis(ps, o, axis=1)
    return idx, sim


def ladr_adaptive(seeds, knn: np.ndarray, dense: np.ndarray, cand_mask: np.ndarray,
                  depth: int = 100, max_iter: int = 50) -> tuple[np.ndarray, int]:
    """Adaptive LADR: returns (top `depth` candidates by dense score among explored docs,
    number of docs scored)."""
    def nbrs(docs):
        n = np.unique(knn[list(docs)].ravel())
        return n[cand_mask[n]]

    seeds = np.asarray([s for s in seeds if cand_mask[s]])
    scored = set(seeds.tolist()) | set(nbrs(seeds).tolist())
    top = None
    for _ in range(max_iter):
        arr = np.fromiter(scored, dtype=np.int64)
        new_top = arr[np.argsort(-dense[arr], kind="stable")][:depth]
        if top is not None and np.array_equal(new_top, top):
            break
        top = new_top
        scored |= set(nbrs(top).tolist())
    return top, len(scored)
