"""Ranking methods for the v2 benchmark.

Score-based methods return one score per candidate; `rank_from_scores` turns
scores into an order with seeded random tie-breaking, so ties never fall back
to the input order (v1 F1/F3). LLM methods report a status for every call.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np

from src import jan
from src.similarity import BATCH_SIZES, DEVICE, _get_model, bm25_similarity, tfidf_similarity

CROSS_ENCODER = "BAAI/bge-reranker-base"
EMBED_METHODS = ("minilm", "specter2", "qwen", "embeddinggemma")

# In-process sentence-transformers models; the rest are served by llama-server (src/jan.py).
# EmbeddingGemma runs here because its GGUF lacks the two Dense projection layers
# (768 -> 3072 -> 768) that follow mean pooling in the released model.
ST_MODELS = {
    "minilm": "all-MiniLM-L6-v2",
    "specter2": "allenai/specter2_base",
    "embeddinggemma": "unsloth/embeddinggemma-300m",
}
# Bump when a method's encoder changes so stale cached vectors are not reused.
CACHE_VERSION = {"specter2": "cls", "embeddinggemma": "st-dense"}
LLM_STATUSES = ("ok", "partial", "parse_fail", "http_error")

# v1 ended this prompt with "e.g.: [3, 1, 7, ...]", which pointed at a positive (F2).
LISTWISE_PROMPT = (
    "You are a research paper relevance ranker.\n\n"
    "Main paper:\n{query}\n\n"
    "Candidate papers:\n{candidates}\n\n"
    "Rank all {n} candidate papers from most to least likely to be cited by the main paper. "
    "Respond ONLY with a JSON array of the candidate numbers, each number exactly once, "
    "most likely first."
)

POINTWISE_PROMPT = (
    "You are a research paper relevance judge.\n\n"
    "Main paper:\n{query}\n\n"
    "Candidate paper:\n{candidate}\n\n"
    "On a scale from 0 to 10, how likely is it that the main paper cites the candidate paper? "
    "Respond ONLY with a single integer from 0 to 10."
)


def rank_from_scores(scores, rng: np.random.Generator) -> list[int]:
    """Indices sorted by score descending; ties broken by a seeded random key."""
    scores = np.asarray(scores, dtype=float)
    return np.lexsort((rng.random(len(scores)), -scores)).tolist()


# ---------------------------------------------------------------------------
# Embeddings (cached per model by text hash, computed once for all queries)
# ---------------------------------------------------------------------------

class EmbeddingCache:
    def __init__(self, method: str, cache_dir: Path):
        self.method = method
        version = CACHE_VERSION.get(method)
        self.path = Path(cache_dir) / (f"{method}__{version}.npz" if version else f"{method}.npz")
        self.vectors: dict[str, np.ndarray] = {}
        if self.path.exists():
            with np.load(self.path) as data:
                self.vectors = {k: data[k] for k in data.files}

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def _encode(self, texts: list[str]) -> np.ndarray:
        if self.method in ST_MODELS:
            name = ST_MODELS[self.method]
            return _get_model(name).encode(texts, batch_size=BATCH_SIZES.get(name, 64),
                                           convert_to_numpy=True, show_progress_bar=True)
        return jan.embed(jan.JAN_MODEL_MAP[self.method], texts)

    def ensure(self, texts) -> None:
        missing = sorted({t for t in texts if self.key(t) not in self.vectors})
        if not missing:
            return
        emb = self._encode(missing)
        self.vectors.update({self.key(t): v for t, v in zip(missing, emb)})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(self.path, **self.vectors)

    def get(self, texts) -> np.ndarray:
        return np.stack([self.vectors[self.key(t)] for t in texts])


def _l2(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.where(norms == 0, 1.0, norms)


def cosine_scores(query_vec: np.ndarray, cand_vecs: np.ndarray) -> np.ndarray:
    return _l2(cand_vecs) @ _l2(query_vec)


def lexical_scores(method: str, query: str, cands: list[str]) -> np.ndarray:
    fn = bm25_similarity if method == "bm25" else tfidf_similarity
    return fn([query], cands)[0]


class CrossEncoderScorer:
    def __init__(self, model_name: str = CROSS_ENCODER):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_name, device=DEVICE, max_length=512)

    def scores(self, query: str, cands: list[str]) -> np.ndarray:
        return np.asarray(self.model.predict([(query, c) for c in cands], batch_size=32))


# ---------------------------------------------------------------------------
# LLM rankers (Jan)
# ---------------------------------------------------------------------------

def listwise_prompt(query: str, cands: list[str], template: str = LISTWISE_PROMPT) -> str:
    lines = "\n".join(f"[{i + 1}] {c}" for i, c in enumerate(cands))
    return template.format(query=query, candidates=lines, n=len(cands))


def parse_listwise(text: str, n: int) -> tuple[list[int], str]:
    """0-based unique indices in the order the model gave them, and a status."""
    start, end = text.find("["), text.find("]", text.find("["))
    if start < 0 or end < 0:
        return [], "parse_fail"
    try:
        nums = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        nums = re.findall(r"\d+", text[start:end + 1])
    seen, order = set(), []
    for x in nums:
        try:
            idx = int(x) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= idx < n and idx not in seen:
            seen.add(idx)
            order.append(idx)
    if not order:
        return [], "parse_fail"
    return order, ("ok" if len(order) == n else "partial")


def listwise_rank(query: str, cands: list[str], rng: np.random.Generator,
                  model: str | None = None, seed: int = 0, template: str = LISTWISE_PROMPT) -> dict:
    """Listwise LLM ranking. Unranked candidates go last in random order; on any
    failure the whole order is random (v1 returned the input order, F3)."""
    model = model or jan.JAN_MODEL_MAP["llama"]
    n = len(cands)
    raw, prompt_tokens = None, None
    try:
        resp = jan.chat(model, listwise_prompt(query, cands, template), max_tokens=8 * n + 32, seed=seed)
        raw, prompt_tokens = resp["text"], resp["prompt_tokens"]
        order, status = parse_listwise(raw, n)
    except jan.JanError as e:
        raw, order, status = str(e), [], "http_error"
    ranked = set(order)
    rest = [i for i in rng.permutation(n).tolist() if i not in ranked]
    return {"order": order + rest, "status": status, "n_ranked": len(order),
            "raw": raw, "prompt_tokens": prompt_tokens}


def sliding_window_rank(query: str, cands: list[str], rng: np.random.Generator,
                        window: int = 10, step: int = 5, model: str | None = None, seed: int = 0) -> dict:
    """RankGPT-style listwise ranking: rerank overlapping windows from the bottom of the
    list to the top, so strong candidates move up while the model never sees more than
    `window` candidates at once."""
    order = list(range(len(cands)))
    starts = list(range(max(len(order) - window, 0), -1, -step))
    if starts[-1] != 0:
        starts.append(0)
    statuses, n_ranked, tokens = [], 0, []
    for start in starts:
        idx = order[start:start + window]
        res = listwise_rank(query, [cands[i] for i in idx], rng, model=model, seed=seed)
        order[start:start + window] = [idx[j] for j in res["order"]]
        statuses.append(res["status"])
        n_ranked += res["n_ranked"]
        tokens.append(res["prompt_tokens"] or 0)
    failed = sum(s in ("parse_fail", "http_error") for s in statuses)
    status = "ok" if all(s == "ok" for s in statuses) else ("parse_fail" if failed == len(statuses) else "partial")
    return {"order": order, "status": status, "n_calls": len(statuses), "window_statuses": statuses,
            "n_ranked": n_ranked, "prompt_tokens": max(tokens) if tokens else None}


def _expected_score(top_logprobs) -> float | None:
    """Probability-weighted 0–10 score from the first token's alternatives."""
    if not top_logprobs:
        return None
    total, weighted = 0.0, 0.0
    for alt in top_logprobs:
        tok = alt.get("token", "").strip()
        if tok.isdigit() and 0 <= int(tok) <= 10:
            p = math.exp(alt["logprob"])
            total += p
            weighted += p * int(tok)
    return weighted / total if total > 0 else None


def pointwise_score(query: str, cand: str, model: str | None = None, seed: int = 0,
                    template: str = POINTWISE_PROMPT) -> dict:
    model = model or jan.JAN_MODEL_MAP["llama"]
    try:
        resp = jan.chat(model, template.format(query=query, candidate=cand),
                        max_tokens=4, seed=seed, top_logprobs=20)
    except jan.JanError as e:
        return {"score": None, "status": "http_error", "raw": str(e)}
    expected = _expected_score(resp["top_logprobs"])
    if expected is not None:
        return {"score": expected, "status": "ok", "raw": resp["text"], "scoring": "logprobs"}
    m = re.search(r"\b(10|[0-9])\b", resp["text"])
    if m:
        return {"score": float(m.group(1)), "status": "ok", "raw": resp["text"], "scoring": "integer"}
    return {"score": None, "status": "parse_fail", "raw": resp["text"]}
