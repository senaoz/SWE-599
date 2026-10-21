from __future__ import annotations

from collections.abc import Sequence

import numpy as np

# How a researcher's score is built from the cosines of their works above the threshold, best first.
# "mean_top3" is the mean of the top min(3, n), as in the research (src/bibcoupling.py).
AGGREGATIONS = {
    "max": lambda s: s[0],
    "mean_top3": lambda s: float(np.mean(s[:3])),
}


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity matrix (len(a), len(b)); zero vectors score 0."""
    def unit(x):
        norms = np.linalg.norm(x, axis=1, keepdims=True)
        return x / np.where(norms == 0, 1.0, norms)
    return (unit(np.asarray(a, dtype=np.float32)) @ unit(np.asarray(b, dtype=np.float32)).T).astype(np.float32)


def rank_researchers(
    scores: np.ndarray,
    researcher_ids: Sequence[str],
    threshold: float,
    top_k: int,
    aggregate: str = "max",
) -> list[tuple[str, float, list[tuple[float, int]]]]:
    """Rank researchers for one new paper from its cosine scores against BOUN paper rows.

    Rows below `threshold` are dropped; a researcher's score aggregates their remaining rows
    (see AGGREGATIONS). Returns at most `top_k` (researcher_id, score, hits) by score, where hits
    are (cosine, row index), best first. Ties keep row order.
    """
    agg = AGGREGATIONS[aggregate]
    hits: dict[str, list[tuple[float, int]]] = {}
    for j, (score, r_id) in enumerate(zip(scores, researcher_ids)):
        score = float(score)
        if score >= threshold:
            hits.setdefault(r_id, []).append((score, j))

    ranked = []
    for r_id, r_hits in hits.items():
        r_hits.sort(key=lambda x: x[0], reverse=True)
        ranked.append((r_id, agg([s for s, _ in r_hits]), r_hits))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


def match_papers(
    paper_embs: np.ndarray,
    boun_embs: np.ndarray,
    researcher_ids: Sequence[str],
    threshold: float,
    top_k: int,
    aggregate: str = "max",
) -> list[list[tuple[str, float, list[tuple[float, int]]]]]:
    """rank_researchers for each new paper (row of paper_embs) against the BOUN paper rows."""
    scores = cosine_matrix(paper_embs, boun_embs)
    return [rank_researchers(row, researcher_ids, threshold, top_k, aggregate) for row in scores]
