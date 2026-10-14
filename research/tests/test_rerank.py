"""Unit tests for the Phase 5 second stage (src/rerank.py)."""
import numpy as np

from src.rerank import fuse_order, minmax


def test_minmax_handles_constant_scores():
    assert minmax(np.array([2.0, 2.0])).tolist() == [0.0, 0.0]
    assert minmax(np.array([1.0, 3.0, 2.0])).tolist() == [0.0, 1.0, 0.5]


def test_fuse_order_extremes():
    order = np.array([10, 11, 12])            # first-stage order
    first = np.array([0.9, 0.8, 0.7])
    llm = np.array([1.0, 5.0, 9.0])
    assert fuse_order(order, llm, first, 0.0).tolist() == [10, 11, 12]
    assert fuse_order(order, llm, first, 1.0).tolist() == [12, 11, 10]


def test_fuse_order_ties_keep_first_stage_order():
    order = np.array([3, 1, 2])
    assert fuse_order(order, np.zeros(3), np.zeros(3), 0.5).tolist() == [3, 1, 2]
