"""Unit tests for src/bibcoupling.py on small synthetic reference sets.

    paper  references
    R      a, b, c, d        the rated paper
    P1     a, b              shares two references with R
    P2     d, e, f, g        shares one reference (d, the rare one) with R
    P3     x, y              shares nothing
"""
import math

import pytest

from src.bibcoupling import (aggregate, bootstrap_ci, coupling, fuse_linear, fuse_rrf, forward_citation,
                             idf_weights, kt_loss, kt_loss_pairs, lopo_select, per_reviewer_loss, reverse_citation, zscore_within)

R = {"a", "b", "c", "d"}
P1 = {"a", "b"}
P2 = {"d", "e", "f", "g"}
P3 = {"x", "y"}


def test_overlap_jaccard_cosine():
    assert coupling(R, P1, "overlap") == 2
    assert coupling(R, P1, "jaccard") == pytest.approx(2 / 4)
    assert coupling(R, P1, "cosine") == pytest.approx(2 / math.sqrt(4 * 2))
    assert coupling(R, P2, "jaccard") == pytest.approx(1 / 7)
    for kind in ("overlap", "jaccard", "cosine"):
        assert coupling(R, P3, kind) == 0
        assert coupling(R, set(), kind) == 0


def test_idf_weights_rare_counts_more():
    w = idf_weights({"common": 99, "rare": 0}, n_docs=99)
    assert w["rare"] == pytest.approx(math.log(100))
    assert w["common"] == 0.0
    assert idf_weights({"over": 500}, n_docs=99)["over"] == 0.0  # floored, never negative


def test_idf_cosine_weights_shared_references():
    idf = {"a": 0.1, "b": 0.1, "c": 1.0, "d": 3.0, "e": 1.0, "f": 1.0, "g": 1.0}
    # P2 shares only d, but d is rare, so it beats P1 (two common shares); plain cosine says the opposite
    assert coupling(R, P2, "idf_cosine", idf) > coupling(R, P1, "idf_cosine", idf)
    assert coupling(R, P1, "cosine") > coupling(R, P2, "cosine")
    expected = 3.0 ** 2 / math.sqrt((0.01 + 0.01 + 1 + 9) * (9 + 3))
    assert coupling(R, P2, "idf_cosine", idf) == pytest.approx(expected)
    assert coupling(R, R, "idf_cosine", idf) == pytest.approx(1.0)
    assert coupling(R, {"zz"}, "idf_cosine", idf) == 0.0  # unweighted work: no division by zero
    with pytest.raises(ValueError):
        coupling(R, P1, "idf_cosine")


def test_aggregations():
    s = [0.1, 0.9, 0.5, 0.3]
    assert aggregate(s, "max") == 0.9
    assert aggregate(s, "mean") == pytest.approx(0.45)
    assert aggregate(s, "top3") == pytest.approx((0.9 + 0.5 + 0.3) / 3)
    assert aggregate([0.4, 0.2], "top3") == pytest.approx(0.3)
    assert aggregate([], "max") == 0.0


def test_forward_and_reverse_citation_are_separate():
    rated_ids = {"W_R", "W_R_arxiv"}
    profile_ids = [{"W_P1"}, {"W_P2", "W_P2_arxiv"}, {"W_P3"}]
    rated_refs = {"W_P2_arxiv", "zz"}          # R cites the preprint of P2
    profile_refs = [{"W_R"}, set(), {"qq"}]    # P1 cites R
    assert forward_citation(rated_refs, profile_ids) == 1
    assert reverse_citation(profile_refs, rated_ids) == 1
    # a reverse citation never shows up as a forward one, and vice versa
    assert forward_citation(set(), profile_ids) == 0
    assert reverse_citation([set(), set(), set()], rated_ids) == 0


REFS = {"u1": {"p1": 5.0, "p2": 3.0, "p3": 1.0}, "u2": {"q1": 4.0, "q2": 2.0}}


def test_kt_loss_perfect_reversed_tied():
    perfect = {"u1": {"p1": 3, "p2": 2, "p3": 1}, "u2": {"q1": 1, "q2": 0}}
    reversed_ = {"u1": {"p1": 1, "p2": 2, "p3": 3}, "u2": {"q1": 0, "q2": 1}}
    tied = {"u1": {"p1": 0, "p2": 0, "p3": 0}, "u2": {"q1": 0, "q2": 0}}
    assert kt_loss(perfect, REFS) == 0
    assert kt_loss(reversed_, REFS) == 1
    assert kt_loss(tied, REFS) == 0.5


def test_kt_loss_is_pooled_not_averaged():
    # u1 wrong on the (p1, p2) pair only: loss 2 of max 2 + 4 + 2 = 8; u2 right: 0 of 2
    preds = {"u1": {"p1": 2, "p2": 3, "p3": 1}, "u2": {"q1": 1, "q2": 0}}
    assert kt_loss(preds, REFS) == pytest.approx(2 / 10)
    assert per_reviewer_loss(preds, REFS) == pytest.approx({"u1": 2 / 8, "u2": 0.0})
    assert kt_loss(preds, REFS, ["u1", "u1"]) == pytest.approx(4 / 16)


def test_bootstrap_ci_is_seeded():
    preds = {"u1": {"p1": 2, "p2": 3, "p3": 1}, "u2": {"q1": 1, "q2": 0}}
    a = bootstrap_ci([preds, preds], REFS, n_boot=50, seed=1)
    assert a == bootstrap_ci([preds, preds], REFS, n_boot=50, seed=1)
    assert a[1] <= a[0] <= a[2]


def test_zscore_and_fusion():
    a = {"u": {"p1": 1.0, "p2": 1.0, "p3": 1.0}}       # constant: carries no order
    b = {"u": {"p1": 0.1, "p2": 0.3, "p3": 0.2}}
    assert zscore_within(a)["u"] == {"p1": 0.0, "p2": 0.0, "p3": 0.0}
    f = fuse_linear(a, b, alpha=0.5)["u"]
    assert sorted(f, key=f.get) == ["p1", "p3", "p2"]
    r = fuse_rrf(a, b, k=60)["u"]
    assert sorted(r, key=r.get) == ["p1", "p3", "p2"]   # tied ranks of a add the same to each


def test_lopo_select_never_uses_held_out_reviewer():
    refs = {"u1": {"a": 2.0, "b": 1.0}, "u2": {"a": 2.0, "b": 1.0}, "u3": {"a": 1.0, "b": 2.0}}
    good = {"u1": {"a": 1, "b": 0}, "u2": {"a": 1, "b": 0}, "u3": {"a": 1, "b": 0}}
    bad = {"u1": {"a": 0, "b": 1}, "u2": {"a": 0, "b": 1}, "u3": {"a": 0, "b": 1}}
    preds, choice = lopo_select(lambda g: [good if g == "good" else bad], ["good", "bad"], refs)
    # Held out u3, "good" still wins on u1 + u2, so u3 gets "good" although "bad" is right for u3.
    assert choice == {"u1": "good", "u2": "good", "u3": "good"}
    assert preds[0]["u3"] == good["u3"]


def test_kt_loss_pairs_restricts_to_kept_pairs():
    preds = {"u1": {"p1": 2, "p2": 3, "p3": 1}, "u2": {"q1": 1, "q2": 0}}
    keep_p1p2 = lambda r, a, b: {a, b} == {"p1", "p2"}
    assert kt_loss_pairs(preds, REFS, keep_p1p2) == (1.0, 1)
    rest = lambda r, a, b: not keep_p1p2(r, a, b)
    assert kt_loss_pairs(preds, REFS, rest) == (0.0, 3)
    loss, n = kt_loss_pairs(preds, REFS, lambda r, a, b: False)
    assert n == 0 and math.isnan(loss)


def test_bootstrap_ci_accepts_labels_per_sample():
    preds = {"u1": {"p1": 3, "p2": 2, "p3": 1}, "u2": {"q1": 1, "q2": 0}}
    flipped = {r: {p: -v for p, v in d.items()} for r, d in REFS.items()}
    point, _, _ = bootstrap_ci([preds, preds], [REFS, flipped], n_boot=20)
    assert point == pytest.approx(0.5)   # perfect on the first labels, reversed on the second
    assert bootstrap_ci([preds], [REFS], n_boot=20) == bootstrap_ci([preds], REFS, n_boot=20)
