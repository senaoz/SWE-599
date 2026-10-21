import numpy as np
import pytest

from backend.services.ranking import match_papers, rank_researchers

# Fixed 3-d vectors: one new paper along x; BOUN rows at known cosines to it.
PAPER = np.array([[1.0, 0.0, 0.0]])


def row(cos):
    return [cos, float(np.sqrt(1 - cos ** 2)), 0.0]


BOUN = np.array([row(0.95), row(0.40), row(0.35), row(0.80), row(0.78), row(0.76), row(0.20), [0.0, 0.0, 0.0]])
IDS = ["a", "a", "a", "b", "b", "b", "c", "d"]


def test_cosine_cut_off_on_fixed_vectors():
    (ranked,) = match_papers(PAPER, BOUN, IDS, threshold=0.3, top_k=10)
    assert [r for r, _, _ in ranked] == ["a", "b"]  # c at 0.20 and the zero vector d are cut
    assert ranked[0][1] == pytest.approx(0.95, abs=1e-6)
    assert [j for _, j in ranked[0][2]] == [0, 1, 2]


def test_threshold_above_everything_gives_no_matches():
    assert match_papers(PAPER, BOUN, IDS, threshold=0.96, top_k=10) == [[]]


def test_top_k_keeps_best_researchers():
    (ranked,) = match_papers(PAPER, BOUN, IDS, threshold=0.3, top_k=1)
    assert [r for r, _, _ in ranked] == ["a"]


def test_aggregation_changes_the_order():
    (by_max,) = match_papers(PAPER, BOUN, IDS, 0.3, 10, aggregate="max")
    (by_top3,) = match_papers(PAPER, BOUN, IDS, 0.3, 10, aggregate="mean_top3")
    assert [r for r, _, _ in by_max] == ["a", "b"]
    assert [r for r, _, _ in by_top3] == ["b", "a"]
    assert dict((r, s) for r, s, _ in by_top3) == pytest.approx({"a": (0.95 + 0.40 + 0.35) / 3, "b": 0.78}, abs=1e-6)


def test_mean_top3_uses_what_is_there():
    out = rank_researchers(np.array([0.9, 0.5]), ["a", "a"], 0.3, 5, aggregate="mean_top3")
    assert out[0][1] == pytest.approx(0.7)


def test_unknown_aggregation_fails():
    with pytest.raises(KeyError):
        rank_researchers(np.array([0.9]), ["a"], 0.3, 5, aggregate="median")


def test_several_papers_rank_independently():
    papers = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    first, second = match_papers(papers, BOUN, IDS, 0.3, 10)
    assert [r for r, _, _ in first] == ["a", "b"]
    assert second == []
