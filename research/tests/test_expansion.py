"""Unit tests for the Phase 5 expansion methods (src/expansion.py)."""
import numpy as np

from src.expansion import grit_expand, knn_graph, ladr_adaptive


def test_grit_keeps_head_and_length_and_fills_from_bottom():
    top = np.array([0, 1, 2, 3])                  # K = 4, b = 0.5 replaces 2 slots
    graph = np.array([0, 0, 0, 0, 5, 0, 1.0])     # only doc 4 is a neighbour; doc 6 is not a candidate
    mask = np.array([True] * 6 + [False])
    tie = np.zeros(7)
    new, added = grit_expand(top, t=2, b=0.5, graph_scores=graph, cand_mask=mask, tie=tie)
    assert new.tolist() == [0, 1, 4, 2] and added.tolist() == [4]


def test_grit_orders_neighbours_by_graph_then_tie_and_skips_kept_docs():
    top = np.array([0, 1, 2, 3])
    graph = np.array([9, 0, 0, 0, 2, 2, 3.0])     # doc 0 is kept, so it is not re-added
    tie = np.array([0, 0, 0, 0, 0.1, 0.9, 0])
    new, added = grit_expand(top, t=1, b=0.5, graph_scores=graph, cand_mask=np.ones(7, bool), tie=tie)
    assert added.tolist() == [6, 5] and new.tolist() == [0, 1, 6, 5]


def test_grit_with_b_zero_is_the_identity():
    top = np.array([3, 1, 2])
    new, added = grit_expand(top, t=1, b=0.0, graph_scores=np.ones(4), cand_mask=np.ones(4, bool), tie=np.zeros(4))
    assert new.tolist() == [3, 1, 2] and len(added) == 0


def test_knn_graph_excludes_self():
    emb = np.array([[1, 0], [0.9, 0.1], [0, 1], [0.1, 0.9]])
    idx, sim = knn_graph(emb, k=1, chunk=2)
    assert idx.ravel().tolist() == [1, 0, 3, 2]


def test_ladr_reaches_the_dense_top_through_the_graph():
    # chain 0-1-2-3-4: seeds {0}; the best dense doc (4) is four hops away
    knn = np.array([[1], [2], [3], [4], [3]])
    dense = np.array([0.0, 0.1, 0.2, 0.3, 0.9])
    top, n_scored = ladr_adaptive([0], knn, dense, np.ones(5, bool), depth=2)
    assert top.tolist() == [4, 3] and n_scored == 5
