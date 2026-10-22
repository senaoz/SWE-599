from __future__ import annotations

from collections.abc import Sequence

import numpy as np

# How a researcher's score is built from the cosines of their works above the threshold, best first.
# "mean_top3" is the mean of the top min(3, n), as in the research (src/bibcoupling.py).
AGGREGATIONS = {
    "max": lambda s: s[0],
    "mean_top3": lambda s: float(np.mean(s[:3])),
}


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


def rank_from_works(
    work_hits: Sequence[tuple[str, float]],
    authors: dict[str, list[str]],
    floor: float,
    top_k: int,
    aggregate: str = "max",
) -> list[tuple[str, float, list[tuple[float, str]]]]:
    """Rank researchers for one new paper from its retrieved BOUN works.

    `work_hits` are (work_id, cosine), best first; `authors` maps a work to its BOUN researchers.
    Each (work, author) pair is one row for rank_researchers. If the best researcher scores below
    `floor`, the paper gets no researchers at all (a paper-level floor, docs/MATCHING_DESIGN.md §4).
    Returns (researcher_id, score, [(cosine, work_id), …]) with the hits best first.
    """
    rows = [(cos, wid, r_id) for wid, cos in work_hits for r_id in authors.get(wid, [])]
    ranked = rank_researchers([c for c, _, _ in rows], [r for _, _, r in rows], float("-inf"), top_k, aggregate)
    if not ranked or ranked[0][1] < floor:
        return []
    return [(r_id, score, [(c, rows[j][1]) for c, j in hits]) for r_id, score, hits in ranked]
