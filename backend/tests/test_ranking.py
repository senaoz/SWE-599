import numpy as np

from backend.services.ranking import rank_researchers


def _old_inline(scores, researcher_ids, threshold, top_k):
    """The grouping both matching jobs did inline before rank_researchers."""
    researcher_hits = {}
    for j, r_id in enumerate(researcher_ids):
        score = float(scores[j])
        if score < threshold:
            continue
        researcher_hits.setdefault(r_id, []).append((score, j))
    ranked = {r: sorted(h, key=lambda x: x[0], reverse=True) for r, h in researcher_hits.items()}
    best = {r: h[0][0] for r, h in ranked.items()}
    top = sorted(best.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [(r, s, ranked[r]) for r, s in top]


def test_threshold_max_and_top_k():
    scores = np.array([0.9, 0.2, 0.5, 0.7, 0.35, 0.29])
    ids = ["a", "a", "b", "b", "c", "d"]
    out = rank_researchers(scores, ids, threshold=0.3, top_k=2)
    assert [(r, round(s, 2)) for r, s, _ in out] == [("a", 0.9), ("b", 0.7)]
    assert [j for _, j in out[1][2]] == [3, 2]
    assert [j for _, j in out[0][2]] == [0]


def test_threshold_is_inclusive_and_empty_when_nothing_passes():
    ids = ["a", "b"]
    assert [r for r, _, _ in rank_researchers(np.array([0.5, 0.3]), ids, 0.3, 5)] == ["a", "b"]
    assert rank_researchers(np.array([0.1, 0.2]), ids, 0.3, 5) == []


def test_ties_keep_row_order():
    out = rank_researchers(np.array([0.6, 0.6, 0.6]), ["c", "a", "b"], 0.3, 3)
    assert [r for r, _, _ in out] == ["c", "a", "b"]


def test_matches_previous_inline_logic():
    rng = np.random.default_rng(0)
    for _ in range(50):
        n = int(rng.integers(1, 200))
        scores = rng.uniform(-0.2, 1.0, n).round(2)
        ids = [f"r{k}" for k in rng.integers(0, 30, n)]
        assert rank_researchers(scores, ids, 0.3, 10) == _old_inline(scores, ids, 0.3, 10)
