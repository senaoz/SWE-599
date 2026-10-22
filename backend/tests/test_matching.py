import numpy as np
import pytest

from backend.services.ranking import rank_from_works, rank_researchers

# Retrieved BOUN works for one new paper, best first, and their BOUN authors.
HITS = [("w1", 0.95), ("w4", 0.80), ("w5", 0.78), ("w6", 0.76), ("w2", 0.40), ("w3", 0.35), ("w7", 0.20)]
AUTHORS = {"w1": ["a"], "w2": ["a"], "w3": ["a"], "w4": ["b"], "w5": ["b"], "w6": ["b"], "w7": ["c"]}


def test_researchers_ranked_by_their_best_work():
    ranked = rank_from_works(HITS, AUTHORS, floor=0.3, top_k=10)
    assert [r for r, _, _ in ranked] == ["a", "b", "c"]
    assert ranked[0][1] == pytest.approx(0.95)
    assert [w for _, w in ranked[0][2]] == ["w1", "w2", "w3"]


def test_floor_is_per_paper_not_per_pair():
    # c's only work is below the floor, but the paper's best researcher is above it, so c stays.
    ranked = rank_from_works(HITS, AUTHORS, floor=0.3, top_k=10)
    assert ranked[-1][0] == "c" and ranked[-1][1] == pytest.approx(0.20)
    assert rank_from_works(HITS, AUTHORS, floor=0.96, top_k=10) == []


def test_top_k_keeps_best_researchers():
    assert [r for r, _, _ in rank_from_works(HITS, AUTHORS, 0.3, top_k=1)] == ["a"]


def test_aggregation_changes_the_order():
    by_top3 = rank_from_works(HITS, AUTHORS, 0.3, 10, aggregate="mean_top3")
    assert [r for r, _, _ in by_top3][:2] == ["b", "a"]
    assert dict((r, s) for r, s, _ in by_top3)["b"] == pytest.approx(0.78)


def test_shared_work_counts_for_every_author():
    ranked = rank_from_works([("w1", 0.9)], {"w1": ["a", "b"]}, 0.3, 10)
    assert sorted(r for r, _, _ in ranked) == ["a", "b"]
    assert all(hits == [(0.9, "w1")] for _, _, hits in ranked)


def test_works_without_boun_authors_are_skipped():
    assert rank_from_works([("w9", 0.99)], {}, 0.3, 10) == []
    ranked = rank_from_works([("w9", 0.99), ("w1", 0.5)], {"w1": ["a"]}, 0.3, 10)
    assert [(r, s) for r, s, _ in ranked] == [("a", 0.5)]


def test_mean_top3_uses_what_is_there():
    out = rank_researchers(np.array([0.9, 0.5]), ["a", "a"], 0.3, 5, aggregate="mean_top3")
    assert out[0][1] == pytest.approx(0.7)


def test_unknown_aggregation_fails():
    with pytest.raises(KeyError):
        rank_researchers(np.array([0.9]), ["a"], 0.3, 5, aggregate="median")
