"""Phase 5 full-corpus first stage (research/audit/PHASE5_DESIGN.md).

Every method scores the whole candidate corpus once per query. A query's candidates
are the corpus works published before it, plus its own positives whatever their date
(decision 4, as in v2), minus records that duplicate the query itself. Rankings use
seeded random tie-breaking, so ties never favour corpus order.
"""
from __future__ import annotations

import numpy as np

from src.eval_v2 import rng_for
from src.metrics import ndcg_at_n
from src.rankers_v2 import EmbeddingCache, rank_from_scores

RECALL_KS = (5, 10, 20, 50, 100)
TOP_STORED = 100


def candidate_mask(doc_days: np.ndarray, qday: int, positive_idx: list[int], exclude_idx: list[int]) -> np.ndarray:
    mask = doc_days < qday
    mask[positive_idx] = True
    mask[exclude_idx] = False
    return mask


def bm25_scores(index, query: str) -> np.ndarray:
    """index: rank_bm25.BM25Okapi over lower-cased whitespace tokens (same tokenization as v2)."""
    return np.asarray(index.get_scores(query.lower().split()))


def tfidf_matrix(doc_texts: list[str], query_texts: list[str]) -> np.ndarray:
    """Query x doc cosine similarity; the vectorizer settings match v2 (src/similarity.py)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    vec = TfidfVectorizer(max_features=50000, stop_words="english")
    m = vec.fit_transform(list(doc_texts) + list(query_texts))
    return cosine_similarity(m[len(doc_texts):], m[:len(doc_texts)])


def dense_matrix(method: str, doc_texts: list[str], query_texts: list[str], cache_dir) -> np.ndarray:
    """Query x doc cosine similarity from cached embeddings (computed on first use)."""
    cache = EmbeddingCache(method, cache_dir)
    cache.ensure(list(doc_texts) + list(query_texts))
    d, q = cache.get(doc_texts), cache.get(query_texts)
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    q = q / np.linalg.norm(q, axis=1, keepdims=True)
    return q @ d.T


def rrf(rank_lists: list[np.ndarray], n_docs: int, k: int = 60) -> np.ndarray:
    """Reciprocal rank fusion of full candidate orderings (arrays of doc indices, best first)."""
    score = np.zeros(n_docs)
    for order in rank_lists:
        score[order] += 1.0 / (k + np.arange(1, len(order) + 1))
    return score


def rank_candidates(scores: np.ndarray, mask: np.ndarray, *seed_parts) -> np.ndarray:
    """Doc indices of the query's candidates, best first, with seeded random tie-breaking."""
    cand = np.flatnonzero(mask)
    order = rank_from_scores(scores[cand], rng_for("phase5-rank", *seed_parts))
    return cand[order]


def query_metrics(order: np.ndarray, positive_idx: list[int]) -> tuple[dict, list[int]]:
    """Recall@k, nDCG@10, MRR and R-precision for one full candidate ordering."""
    pos = set(positive_idx)
    n = len(pos)
    ranks = np.flatnonzero(np.isin(order, list(pos))) + 1  # 1-based ranks of the positives
    out = {f"recall@{k}": float((ranks <= k).sum() / n) for k in RECALL_KS}
    out["ndcg@10"] = ndcg_at_n([(i, 0.0) for i in order[:10]], pos, 10)
    out["mrr"] = float(1.0 / ranks.min()) if len(ranks) else 0.0
    out["rprec"] = float((ranks <= n).sum() / n * 100)
    return out, ranks.tolist()
