"""Phase 5 second stage: pointwise LLM scores for first-stage lists (task 5.8).

Pointwise scoring sees one (query, candidate) pair per call at temperature 0, so a
score does not depend on list order or on which list the candidate came from. Scores
are cached per (query, doc) in a JSONL file, so overlapping lists are scored once and
an interrupted run resumes.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.rankers_v2 import pointwise_score


class PointwiseCache:
    def __init__(self, path: Path, model: str | None = None):
        self.path, self.model = Path(path), model
        self.scores: dict[tuple[str, str], dict] = {}
        if self.path.exists():
            with self.path.open() as f:
                for r in map(json.loads, f):
                    self.scores[(r["pi_id"], r["doc"])] = r

    def ensure(self, qid: str, query_text: str, docs: list[str], doc_text) -> int:
        """Score every doc not yet cached for this query; returns the number of new calls."""
        todo = [d for d in docs if (qid, d) not in self.scores]
        if not todo:
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            for d in todo:
                out = pointwise_score(query_text, doc_text(d), model=self.model)
                rec = {"pi_id": qid, "doc": d, "score": out["score"], "status": out["status"],
                       "scoring": out.get("scoring")}
                self.scores[(qid, d)] = rec
                f.write(json.dumps(rec) + "\n")
                f.flush()
        return len(todo)

    def get(self, qid: str, docs: list[str]) -> np.ndarray:
        """Scores in `docs` order; a failed call scores -1 (below every valid 0–10 score)."""
        return np.array([s if (s := self.scores[(qid, d)]["score"]) is not None else -1.0 for d in docs])


def minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = x.min(), x.max()
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x, dtype=float)


def fuse_order(order: np.ndarray, llm: np.ndarray, first: np.ndarray, alpha: float) -> np.ndarray:
    """Rerank one list by alpha * llm + (1 - alpha) * first-stage score, both min-max
    normalized within the list; ties keep the first-stage order."""
    s = alpha * minmax(llm) + (1 - alpha) * minmax(first)
    return order[np.lexsort((np.arange(len(order)), -s))]
