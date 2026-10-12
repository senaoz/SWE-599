"""v2 pipeline steps, called from the numbered notebooks in research/v2/.

Outputs (one JSON line per query, resumable):
    v2/eval_sets/eval_sets_<bench>.json
    v2/runs/<bench>/<text tag>/<method>__<order>__s<seed>.jsonl
"""
from __future__ import annotations

import ast
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from src import jan
from src.eval_v2 import assign_splits, build_eval_sets, candidate_order, paper_text, rng_for
from src.metrics import ranking_metrics
from src.openalex import fetch_works_by_id, normalize_work
from src.rankers_v2 import (EMBED_METHODS, CrossEncoderScorer, EmbeddingCache, cosine_scores,
                            lexical_scores, listwise_rank, pointwise_score, rank_from_scores)

RESEARCH = Path(__file__).resolve().parents[1]
V1_QUERIES = RESEARCH / "v1" / "results" / "main_papers.json"
V2 = RESEARCH / "v2"
RAW_WORKS = RESEARCH / "data" / "v2" / "openalex_works.jsonl"
EMB_CACHE = RESEARCH / "data" / "v2" / "embeddings"

METHODS = ("bm25", "tfidf", *EMBED_METHODS, "qwen+minilm", "bge-reranker",
           "llama", "llama-pointwise", "qwen→llama", "llama+minilm")
LLM_METHODS = ("llama", "llama-pointwise", "qwen→llama")
FIELD_CODES = {"t": "title", "a": "abstract", "c": "concepts"}


@dataclass
class RunConfig:
    bench: str
    fields: str = "ta"            # any of t(itle) a(bstract) c(oncepts)
    max_chars: int = 600          # per candidate
    query_max_chars: int = 1500
    split: str = "dev"            # dev | test | all
    orders: list[str] = field(default_factory=lambda: ["shuffled"])
    seeds: list[int] = field(default_factory=lambda: [0])
    stage1_k: int = 20
    stage2_order: str = "shuffled"  # shuffled | stage1
    limit: int | None = None

    @property
    def tag(self) -> str:
        return f"{self.fields}_{self.max_chars}_{self.query_max_chars}"


# ---------------------------------------------------------------------------
# Step 01–02: fetch and build
# ---------------------------------------------------------------------------

def load_v1_queries() -> list[dict]:
    queries = json.loads(V1_QUERIES.read_text(encoding="utf-8"))
    for q in queries:
        if isinstance(q["referenced_works"], str):
            q["referenced_works"] = ast.literal_eval(q["referenced_works"])
    return queries


def fetch_all() -> tuple[list[dict], dict[str, dict], set[str]]:
    """Fetch the v1 query papers and every listed reference. Returns (queries, papers, missing ids)."""
    queries = load_v1_queries()
    ids = {q["id"] for q in queries} | {r for q in queries for r in q["referenced_works"]}
    raw = fetch_works_by_id(ids, RAW_WORKS)
    papers = {pid: normalize_work(w) for pid, w in raw.items()}
    return queries, papers, ids - set(raw)


def eval_sets_path(bench: str) -> Path:
    return V2 / "eval_sets" / f"eval_sets_{bench}.json"


def build(bench: str, queries: list[dict], papers: dict[str, dict], seed: int = 0) -> dict:
    ds = build_eval_sets(queries, papers, seed=seed, bench=bench)
    ds["splits"] = assign_splits(ds["sets"], seed=seed)
    path = eval_sets_path(bench)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ds, indent=1, ensure_ascii=False), encoding="utf-8")
    return ds


def load_eval_sets(bench: str) -> dict:
    path = eval_sets_path(bench)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run v2/02_build_eval_sets.ipynb first")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Step 03–04: run methods
# ---------------------------------------------------------------------------

class Texts:
    def __init__(self, papers: dict, cfg: RunConfig):
        self.papers = papers
        self.fields = tuple(FIELD_CODES[c] for c in cfg.fields)
        self.max_chars, self.query_max_chars = cfg.max_chars, cfg.query_max_chars

    def query(self, pid: str) -> str:
        return paper_text(self.papers[pid], self.fields, self.query_max_chars)

    def cand(self, pid: str) -> str:
        return paper_text(self.papers[pid], self.fields, self.max_chars)


def select_sets(ds: dict, split: str, limit: int | None = None) -> list[dict]:
    sets = [s for s in ds["sets"] if split == "all" or ds["splits"][s["pi_id"]] == split]
    return sets[:limit] if limit else sets


def method_name(method: str, cfg: RunConfig) -> str:
    return f"{method}_k{cfg.stage1_k}_{cfg.stage2_order}" if method == "qwen→llama" else method


def run_path(cfg: RunConfig, method: str, order: str, seed: int) -> Path:
    return V2 / "runs" / cfg.bench / cfg.tag / f"{method_name(method, cfg)}__{order}__s{seed}.jsonl"


def read_run(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {r["pi_id"]: r for r in map(json.loads, f)}


class Scorer:
    """Per-method scoring with heavy resources (embeddings, cross-encoder) loaded once."""

    def __init__(self, method: str, texts: Texts, sets: list[dict], cfg: RunConfig):
        self.method, self.texts, self.cfg = method, texts, cfg
        self.caches: dict[str, EmbeddingCache] = {}
        embed_needs = {"qwen+minilm": ("qwen", "minilm"), "qwen→llama": ("qwen",),
                       "llama+minilm": ("minilm",)}.get(method, (method,) if method in EMBED_METHODS else ())
        all_texts = {texts.query(s["pi_id"]) for s in sets} | {
            texts.cand(c) for s in sets for c in s["positives"] + s["negatives"]}
        for m in embed_needs:
            self.caches[m] = EmbeddingCache(m, EMB_CACHE / cfg.tag)
            self.caches[m].ensure(all_texts)  # all embeddings before any LLM call (Jan swaps models)
        self.cross = CrossEncoderScorer() if method == "bge-reranker" else None

    def embed_scores(self, m: str, query: str, cands: list[str]) -> np.ndarray:
        c = self.caches[m]
        return cosine_scores(c.get([query])[0], c.get(cands))

    def __call__(self, es: dict, shown: list[str], order: str, seed: int) -> dict:
        m, q = self.method, self.texts.query(es["pi_id"])
        cands = [self.texts.cand(c) for c in shown]
        rng = rng_for("rank", m, es["pi_id"], order, seed)
        rec: dict = {}

        if m in ("bm25", "tfidf"):
            scores = lexical_scores(m, q, cands)
        elif m in EMBED_METHODS:
            scores = self.embed_scores(m, q, cands)
        elif m == "qwen+minilm":
            # Mean of cosines == cosine of the concatenated L2-normalized vectors (v1 definition).
            scores = (self.embed_scores("qwen", q, cands) + self.embed_scores("minilm", q, cands)) / 2
        elif m == "bge-reranker":
            scores = self.cross.scores(q, cands)
        elif m == "llama-pointwise":
            outs = [pointwise_score(q, c, seed=seed) for c in cands]
            scores = np.array([o["score"] if o["score"] is not None else -1.0 for o in outs])
            statuses = [o["status"] for o in outs]
            rec = {"status": "ok" if all(s == "ok" for s in statuses) else "partial",
                   "n_failed": sum(s != "ok" for s in statuses),
                   "scoring": sorted({o.get("scoring", "none") for o in outs}),
                   "raw": [o["raw"] for o in outs]}
        elif m == "llama":
            res = listwise_rank(q, cands, rng, seed=seed)
            n = len(cands)
            scores = np.zeros(n)
            for rank, idx in enumerate(res["order"]):
                scores[idx] = (n - rank) / n
            rec = {k: res[k] for k in ("status", "n_ranked", "raw", "prompt_tokens")}
            return {**rec, "ranking": [shown[i] for i in res["order"]], "scores": scores.tolist()}
        elif m == "qwen→llama":
            return self.two_stage(q, cands, shown, rng, seed)
        elif m == "llama+minilm":
            llama = read_run(run_path(self.cfg, "llama", order, seed)).get(es["pi_id"])
            if llama is None:
                raise RuntimeError("llama+minilm needs the llama run for the same config/order/seed")
            llama_scores = dict(zip(llama["shown"], llama["scores"]))
            ls = np.array([llama_scores[c] for c in shown])
            ms = self.embed_scores("minilm", q, cands)
            mm = lambda a: (a - a.min()) / (a.max() - a.min() + 1e-9)  # noqa: E731
            scores = (mm(ls) + mm(ms)) / 2
            rec = {"status": llama["status"]}
        else:
            raise ValueError(m)

        order_idx = rank_from_scores(scores, rng)
        return {**rec, "ranking": [shown[i] for i in order_idx], "scores": np.asarray(scores).tolist()}

    def two_stage(self, q, cands, shown, rng, seed) -> dict:
        k = self.cfg.stage1_k
        s1 = self.embed_scores("qwen", q, cands)
        s1_order = rank_from_scores(s1, rng)
        top = s1_order[:k]
        # Stage-2 input order: shuffled by default so the LLM cannot exploit stage-1 order.
        if self.cfg.stage2_order == "shuffled":
            top = [top[i] for i in rng.permutation(len(top))]
        res = listwise_rank(q, [cands[i] for i in top], rng, seed=seed)
        final = [top[i] for i in res["order"]] + s1_order[k:]
        return {"ranking": [shown[i] for i in final], "stage1_ranking": [shown[i] for i in s1_order],
                **{key: res[key] for key in ("status", "n_ranked", "raw", "prompt_tokens")}}


def check_jan(methods) -> list[str]:
    """Fail fast if a method needs a Jan model that is not served."""
    needed = {jan.JAN_MODEL_MAP["llama"]} if any(m in LLM_METHODS for m in methods) else set()
    needed |= {jan.JAN_MODEL_MAP[m] for m in methods if m in ("qwen", "embeddinggemma")}
    if {"qwen+minilm", "qwen→llama"} & set(methods):
        needed.add(jan.JAN_MODEL_MAP["qwen"])
    if not needed:
        return []
    available = set(jan.list_models())
    missing = needed - available
    if missing:
        raise RuntimeError(f"Jan models not found: {sorted(missing)}. Available: {sorted(available)}")
    return sorted(needed)


def run_methods(methods: list[str], cfg: RunConfig) -> pd.DataFrame:
    """Run (or resume) every method x order x seed; returns one summary row per run file."""
    ds = load_eval_sets(cfg.bench)
    sets = select_sets(ds, cfg.split, cfg.limit)
    texts = Texts(ds["papers"], cfg)
    check_jan(methods)

    for method in methods:
        scorer = Scorer(method, texts, sets, cfg)
        for order in cfg.orders:
            for seed in cfg.seeds:
                path = run_path(cfg, method, order, seed)
                done = read_run(path)
                todo = [s for s in sets if s["pi_id"] not in done]
                if not todo:
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    for es in tqdm(todo, desc=f"{cfg.bench} {method} {order} s{seed}"):
                        shown = candidate_order(es, order, seed)
                        t0 = time.time()
                        out = scorer(es, shown, order, seed)
                        rec = {
                            "pi_id": es["pi_id"], "split": ds["splits"][es["pi_id"]],
                            "method": method_name(method, cfg), "order": order, "seed": seed,
                            "bench": cfg.bench, "text_tag": cfg.tag,
                            "n_pos": len(es["positives"]), "n_cand": len(shown),
                            "shown": shown, "positives": es["positives"],
                            "status": "ok", "seconds": round(time.time() - t0, 3), **out,
                            "metrics": ranking_metrics(out["ranking"], es["positives"]),
                        }
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        f.flush()
    return summarize(load_runs(cfg.bench, cfg.tag, split=cfg.split, methods=[method_name(m, cfg) for m in methods]))


# ---------------------------------------------------------------------------
# Loading results
# ---------------------------------------------------------------------------

def load_runs(bench: str, tag: str | None = None, split: str | None = None,
              methods: list[str] | None = None) -> pd.DataFrame:
    """Per-query rows (one per method x order x seed x query) with flattened metrics."""
    rows = []
    base = V2 / "runs" / bench
    for path in sorted(base.glob(f"{tag or '*'}/*.jsonl")):
        for r in read_run(path).values():
            if split not in (None, "all") and r["split"] != split:
                continue
            if methods and r["method"] not in methods:
                continue
            rows.append({k: r.get(k) for k in ("pi_id", "split", "method", "order", "seed", "text_tag",
                                                "n_pos", "n_cand", "status", "n_ranked", "seconds")}
                        | {"bench": bench} | r["metrics"])
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Mean metrics per run, plus LLM status counts."""
    if df.empty:
        return df
    keys = ["bench", "text_tag", "method", "order", "seed"]
    out = df.groupby(keys).agg(
        queries=("pi_id", "size"), mrr=("mrr", "mean"), rprec=("rprec", "mean"),
        ndcg=("ndcg", "mean"), ap=("ap", "mean"), top1=("top1", "mean"),
        ok=("status", lambda s: int((s == "ok").sum())),
        partial=("status", lambda s: int((s == "partial").sum())),
        failed=("status", lambda s: int(s.isin(["parse_fail", "http_error"]).sum())),
        sec_per_query=("seconds", "mean"),
    ).reset_index()
    return out.round(3)


# ---------------------------------------------------------------------------
# Timing probe
# ---------------------------------------------------------------------------

def probe(cfg: RunConfig, method: str = "llama", n: int = 5) -> pd.DataFrame:
    """Time a few LLM calls on the largest pools (worst case) and print an estimate."""
    ds = load_eval_sets(cfg.bench)
    sets = select_sets(ds, "all")
    texts = Texts(ds["papers"], cfg)
    check_jan([method])
    sample = sorted(sets, key=lambda s: -len(s["positives"]))[:n]
    rng = np.random.default_rng(0)
    rows = []
    for es in sample:
        shown = candidate_order(es, "shuffled", 0)
        q, cands = texts.query(es["pi_id"]), [texts.cand(c) for c in shown]
        t0 = time.time()
        if method == "llama":
            res = listwise_rank(q, cands, rng)
            rows.append({"n_cand": len(cands), "status": res["status"], "n_ranked": res["n_ranked"],
                         "prompt_tokens": res["prompt_tokens"], "seconds": time.time() - t0})
        else:
            outs = [pointwise_score(q, c) for c in cands[:10]]
            rows.append({"n_cand": 10, "status": ",".join(sorted({o["status"] for o in outs})),
                         "scoring": ",".join(sorted({str(o.get("scoring")) for o in outs})),
                         "seconds": time.time() - t0})
    df = pd.DataFrame(rows)
    n_cands = sum(len(s["positives"]) + len(s["negatives"]) for s in sets)
    if method == "llama":
        per = df["seconds"].mean()
        print(f"~{per:.1f}s/call on the largest pools; {len(sets)} queries x 1 seed <= {per * len(sets) / 60:.0f} min")
    else:
        per = df["seconds"].sum() / df["n_cand"].sum()
        print(f"~{per:.2f}s/candidate; all {n_cands} candidates <= {per * n_cands / 60:.0f} min")
    return df
