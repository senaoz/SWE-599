"""Evaluation metrics for information retrieval.

Two paradigms:

ID-based  — suited for large-corpus retrieval where papers are identified by
            string IDs (used in similarity_evaluation.ipynb).
            Functions: ndcg_at_k, average_precision_at_k, reciprocal_rank_fusion

Index-based — suited for small candidate-set ranking where results are
              (index, score) tuples (used in week3_cited_paper_ranking.ipynb).
              Functions: hit_rate_at_n, reciprocal_rank, ndcg_at_n
"""

import math
from collections import defaultdict

import numpy as np


# ---------------------------------------------------------------------------
# ID-based metrics
# ---------------------------------------------------------------------------

def ndcg_at_k(retrieved_ids, positive_id_set, k):
    """NDCG@k with binary relevance, ID-based.

    Parameters
    ----------
    retrieved_ids : list of str
        Ordered list of retrieved paper IDs.
    positive_id_set : set of str
        Ground-truth relevant paper IDs.
    k : int
    """
    dcg = 0.0
    for i, rid in enumerate(retrieved_ids[:k]):
        if rid in positive_id_set:
            dcg += 1.0 / np.log2(i + 2)
    n_relevant = min(len(positive_id_set), k)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(n_relevant))
    return dcg / idcg if idcg > 0 else 0.0


def average_precision_at_k(retrieved_ids, positive_id_set, k):
    """Average Precision@k for a single query, ID-based."""
    hits = 0
    sum_precisions = 0.0
    for i, rid in enumerate(retrieved_ids[:k], 1):
        if rid in positive_id_set:
            hits += 1
            sum_precisions += hits / i
    return sum_precisions / min(len(positive_id_set), k) if positive_id_set else 0.0


def reciprocal_rank_fusion(rankings_list, top_k=10, k=60):
    """Fuse multiple rankings using Reciprocal Rank Fusion (RRF).

    Parameters
    ----------
    rankings_list : list of list of (index, score)
    top_k : int
        Number of results to return.
    k : int
        RRF constant (default 60).

    Returns
    -------
    list of (index, rrf_score) sorted descending
    """
    rrf_scores: dict = defaultdict(float)
    for rankings in rankings_list:
        for rank, (idx, _) in enumerate(rankings, 1):
            rrf_scores[idx] += 1.0 / (k + rank)
    return sorted(rrf_scores.items(), key=lambda x: -x[1])[:top_k]


# ---------------------------------------------------------------------------
# Index-based metrics
# ---------------------------------------------------------------------------

def hit_rate_at_n(ranked, positive_indices, n):
    """Fraction of top-n retrieved that are true positives.

    Parameters
    ----------
    ranked : list of (idx, score)
    positive_indices : set of int
    n : int
    """
    top_n = [idx for idx, _ in ranked[:n]]
    return sum(1 for idx in top_n if idx in positive_indices) / n


def reciprocal_rank(ranked, positive_indices):
    """1 / rank of the first positive in ranked list.

    Parameters
    ----------
    ranked : list of (idx, score)
    positive_indices : set of int
    """
    for rank, (idx, _) in enumerate(ranked, start=1):
        if idx in positive_indices:
            return 1.0 / rank
    return 0.0


def ndcg_at_n(ranked, positive_indices, n):
    """nDCG@n with binary relevance, index-based.

    Parameters
    ----------
    ranked : list of (idx, score)
    positive_indices : set of int
    n : int
    """
    def dcg(hits):
        return sum(h / math.log2(i + 2) for i, h in enumerate(hits))

    top_n_hits = [1 if idx in positive_indices else 0 for idx, _ in ranked[:n]]
    ideal_hits = sorted(top_n_hits, reverse=True)
    ideal_dcg = dcg(ideal_hits)
    return dcg(top_n_hits) / ideal_dcg if ideal_dcg > 0 else 0.0
