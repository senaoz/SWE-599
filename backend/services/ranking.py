from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def rank_researchers(
    scores: np.ndarray,
    researcher_ids: Sequence[str],
    threshold: float,
    top_k: int,
) -> list[tuple[str, float, list[tuple[float, int]]]]:
    """Rank researchers for one new paper from its cosine scores against BOUN paper rows.

    Rows below `threshold` are dropped; a researcher's score is their best row. Returns at most
    `top_k` (researcher_id, score, hits) by score, where hits are (cosine, row index), best first.
    Ties keep row order.
    """
    hits: dict[str, list[tuple[float, int]]] = {}
    for j, (score, r_id) in enumerate(zip(scores, researcher_ids)):
        score = float(score)
        if score >= threshold:
            hits.setdefault(r_id, []).append((score, j))

    ranked = []
    for r_id, r_hits in hits.items():
        r_hits.sort(key=lambda x: x[0], reverse=True)
        ranked.append((r_id, r_hits[0][0], r_hits))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
