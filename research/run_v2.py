"""v2 benchmark runner. Run from research/ with the project venv:

    .venv/bin/python run_v2.py build --bench random
    .venv/bin/python run_v2.py run --bench concept --methods bm25 tfidf minilm --split dev
    .venv/bin/python run_v2.py run --bench concept --methods llama --seeds 0 1 2 3 4 --split test
    .venv/bin/python run_v2.py probe --bench concept --method llama --n 5

Outputs (one JSON line per query, resumable):
    eval_dataset/v2/eval_sets_<bench>.json
    eval_dataset/v2/runs/<bench>/<text tag>/<method>__<order>__s<seed>.jsonl
"""
from __future__ import annotations

import argparse
import ast
import json
import time
from pathlib import Path

import numpy as np
from tqdm.auto import tqdm

from src import jan
from src.eval_v2 import (BENCHES, ORDER_MODES, assign_splits, build_eval_sets, candidate_order,
                         paper_text, rng_for)
from src.metrics import ranking_metrics
from src.openalex import fetch_works_by_id, normalize_work
from src.rankers_v2 import (EMBED_METHODS, CrossEncoderScorer, EmbeddingCache, cosine_scores,
                            lexical_scores, listwise_rank, pointwise_score, rank_from_scores)

ROOT = Path(__file__).resolve().parent
V1_QUERIES = ROOT / "eval_dataset" / "week3" / "main_papers.json"
OUT = ROOT / "eval_dataset" / "v2"
RAW_WORKS = ROOT / "data" / "v2" / "openalex_works.jsonl"
EMB_CACHE = ROOT / "data" / "v2" / "embeddings"

METHODS = ("bm25", "tfidf", *EMBED_METHODS, "qwen+minilm", "bge-reranker",
           "llama", "llama-pointwise", "qwen→llama", "llama+minilm")
LLM_METHODS = ("llama", "llama-pointwise", "qwen→llama")
FIELD_CODES = {"t": "title", "a": "abstract", "c": "concepts"}


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def load_v1_queries() -> list[dict]:
    queries = json.loads(V1_QUERIES.read_text(encoding="utf-8"))
    for q in queries:
        if isinstance(q["referenced_works"], str):
            q["referenced_works"] = ast.literal_eval(q["referenced_works"])
    return queries


def cmd_build(args) -> None:
    queries = load_v1_queries()
    ids = {q["id"] for q in queries} | {r for q in queries for r in q["referenced_works"]}
    raw = fetch_works_by_id(ids, RAW_WORKS)
    papers = {pid: normalize_work(w) for pid, w in raw.items()}
    ds = build_eval_sets(queries, papers, seed=args.seed, bench=args.bench)
    ds["splits"] = assign_splits(ds["sets"], seed=args.seed)
    ds["n_ids_requested"] = len(ids)
    ds["n_ids_missing_from_openalex"] = len(ids - set(raw))
    OUT.mkdir(parents=True, exist_ok=True)
    path = eval_sets_path(args.bench)
    path.write_text(json.dumps(ds, indent=1, ensure_ascii=False), encoding="utf-8")
    n_dev = sum(v == "dev" for v in ds["splits"].values())
    topped = sum(s["n_neg_concept_matched"] is not None
                 and s["n_neg_concept_matched"] < len(s["negatives"]) for s in ds["sets"])
    print(f"{len(ds['sets'])} queries ({n_dev} dev / {len(ds['sets']) - n_dev} test), "
          f"{len(ds['dropped'])} dropped, {len(ds['papers'])} papers, "
          f"{topped} topped up with random negatives -> {path}")


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

class Texts:
    def __init__(self, papers: dict, fields: str, max_chars: int, query_max_chars: int):
        self.papers = papers
        self.fields = tuple(FIELD_CODES[c] for c in fields)
        self.max_chars, self.query_max_chars = max_chars, query_max_chars
        self.tag = f"{fields}_{max_chars}_{query_max_chars}"

    def query(self, pid: str) -> str:
        return paper_text(self.papers[pid], self.fields, self.query_max_chars)

    def cand(self, pid: str) -> str:
        return paper_text(self.papers[pid], self.fields, self.max_chars)


def eval_sets_path(bench: str) -> Path:
    return OUT / f"eval_sets_{bench}.json"


def load_eval_sets(bench: str) -> dict:
    path = eval_sets_path(bench)
    if not path.exists():
        raise SystemExit(f"{path} not found; run `run_v2.py build --bench {bench}` first")
    return json.loads(path.read_text(encoding="utf-8"))


def select_sets(ds: dict, split: str, limit: int | None) -> list[dict]:
    sets = [s for s in ds["sets"] if split == "all" or ds["splits"][s["pi_id"]] == split]
    return sets[:limit] if limit else sets


def run_path(bench: str, tag: str, method: str, order: str, seed: int, suffix: str = "") -> Path:
    return OUT / "runs" / bench / tag / f"{method}{suffix}__{order}__s{seed}.jsonl"


def read_run(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {r["pi_id"]: r for r in map(json.loads, f)}


class Scorer:
    """Per-method scoring with heavy resources (embeddings, cross-encoder) loaded once."""

    def __init__(self, method: str, texts: Texts, sets: list[dict], args):
        self.method, self.texts, self.args = method, texts, args
        self.caches: dict[str, EmbeddingCache] = {}
        embed_needs = {"qwen+minilm": ("qwen", "minilm"), "qwen→llama": ("qwen",),
                       "llama+minilm": ("minilm",)}.get(method, (method,) if method in EMBED_METHODS else ())
        all_texts = {texts.query(s["pi_id"]) for s in sets} | {
            texts.cand(c) for s in sets for c in s["positives"] + s["negatives"]}
        for m in embed_needs:
            self.caches[m] = EmbeddingCache(m, EMB_CACHE / texts.tag)
            self.caches[m].ensure(all_texts)  # all embeddings before any LLM call (Jan loads one model at a time)
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
            llama = read_run(run_path(self.args.bench, self.texts.tag, "llama", order, seed)).get(es["pi_id"])
            if llama is None:
                raise SystemExit("llama+minilm needs the llama run for the same tag/order/seed")
            llama_scores = dict(zip(llama["shown"], llama["scores"]))
            ls = np.array([llama_scores[c] for c in shown])
            ms = self.embed_scores("minilm", q, cands)
            mm = lambda a: (a - a.min()) / (a.max() - a.min() + 1e-9)
            scores = (mm(ls) + mm(ms)) / 2
            rec = {"status": llama["status"]}
        else:
            raise ValueError(m)

        order_idx = rank_from_scores(scores, rng)
        return {**rec, "ranking": [shown[i] for i in order_idx], "scores": np.asarray(scores).tolist()}

    def two_stage(self, q, cands, shown, rng, seed) -> dict:
        s1 = self.embed_scores("qwen", q, cands)
        s1_order = rank_from_scores(s1, rng)
        top = s1_order[: self.args.stage1_k]
        # Stage-2 input order: shuffled by default so the LLM cannot exploit stage-1 order.
        if self.args.stage2_order == "shuffled":
            top = [top[i] for i in rng.permutation(len(top))]
        res = listwise_rank(q, [cands[i] for i in top], rng, seed=seed)
        final = [top[i] for i in res["order"]] + s1_order[self.args.stage1_k:]
        return {"ranking": [shown[i] for i in final], "stage1_ranking": [shown[i] for i in s1_order],
                **{k: res[k] for k in ("status", "n_ranked", "raw", "prompt_tokens")}}


def cmd_run(args) -> None:
    ds = load_eval_sets(args.bench)
    sets = select_sets(ds, args.split, args.limit)
    texts = Texts(ds["papers"], args.fields, args.max_chars, args.query_max_chars)
    if any(m in LLM_METHODS for m in args.methods):
        check_jan(args.methods)

    for method in args.methods:
        suffix = f"_k{args.stage1_k}_{args.stage2_order}" if method == "qwen→llama" else ""
        scorer = Scorer(method, texts, sets, args)
        for order in args.orders:
            for seed in args.seeds:
                path = run_path(args.bench, texts.tag, method, order, seed, suffix)
                done = read_run(path)
                todo = [s for s in sets if s["pi_id"] not in done]
                if not todo:
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    for es in tqdm(todo, desc=f"{method} {order} s{seed}"):
                        shown = candidate_order(es, order, seed)
                        t0 = time.time()
                        out = scorer(es, shown, order, seed)
                        rec = {
                            "pi_id": es["pi_id"], "split": ds["splits"][es["pi_id"]],
                            "method": method + suffix, "order": order, "seed": seed, "text_tag": texts.tag,
                            "n_pos": len(es["positives"]), "n_cand": len(shown),
                            "shown": shown, "positives": es["positives"],
                            "status": "ok", "seconds": round(time.time() - t0, 3), **out,
                            "metrics": ranking_metrics(out["ranking"], es["positives"]),
                        }
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        f.flush()
                report_status(path)


def report_status(path: Path) -> None:
    rows = list(read_run(path).values())
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    mrr = np.mean([r["metrics"]["mrr"] for r in rows])
    print(f"  {path.relative_to(OUT)}: {len(rows)} queries, MRR {mrr:.3f}, status {counts}")


def check_jan(methods) -> None:
    try:
        available = set(jan.list_models())
    except jan.JanError as e:
        raise SystemExit(f"Jan API not reachable at {jan.JAN_URL}: {e}")
    needed = {jan.JAN_MODEL_MAP["llama"]}
    if "qwen→llama" in methods:
        needed.add(jan.JAN_MODEL_MAP["qwen"])
    missing = needed - available
    if missing:
        raise SystemExit(f"Jan models not found: {sorted(missing)}. Available: {sorted(available)}")


# ---------------------------------------------------------------------------
# probe: time a few LLM calls and extrapolate
# ---------------------------------------------------------------------------

def cmd_probe(args) -> None:
    ds = load_eval_sets(args.bench)
    sets = select_sets(ds, "all", None)
    texts = Texts(ds["papers"], args.fields, args.max_chars, args.query_max_chars)
    check_jan([args.method])
    sample = sorted(sets, key=lambda s: -len(s["positives"]))[: args.n]  # largest pools: worst case
    rng = np.random.default_rng(0)
    timings, tokens = [], []
    for es in sample:
        shown = candidate_order(es, "shuffled", 0)
        q, cands = texts.query(es["pi_id"]), [texts.cand(c) for c in shown]
        t0 = time.time()
        if args.method == "llama":
            res = listwise_rank(q, cands, rng)
            tokens.append(res["prompt_tokens"])
            print(f"  n_cand={len(cands)} status={res['status']} ranked={res['n_ranked']} "
                  f"prompt_tokens={res['prompt_tokens']} {time.time() - t0:.1f}s")
        else:
            outs = [pointwise_score(q, c) for c in cands[:10]]
            print(f"  10 pointwise calls, statuses={[o['status'] for o in outs]}, "
                  f"scoring={sorted({o.get('scoring') for o in outs})} {time.time() - t0:.1f}s")
        timings.append(time.time() - t0)
    per = float(np.mean(timings))
    n_cands = sum(len(s["positives"]) + len(s["negatives"]) for s in sets)
    if args.method == "llama":
        print(f"max prompt tokens {max(t or 0 for t in tokens)}; ~{per:.1f}s/call (largest pools); "
              f"{len(sets)} queries x 1 seed <= {per * len(sets) / 60:.0f} min")
    else:
        print(f"~{per / 10:.2f}s/candidate; all {n_cands} candidates <= {per / 10 * n_cands / 60:.0f} min")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--bench", choices=BENCHES, required=True)

    def text_args(p):
        p.add_argument("--bench", choices=BENCHES, required=True)
        p.add_argument("--fields", default="ta", help="any of t(itle) a(bstract) c(oncepts)")
        p.add_argument("--max-chars", type=int, default=600)
        p.add_argument("--query-max-chars", type=int, default=1500)

    r = sub.add_parser("run")
    r.add_argument("--methods", nargs="+", choices=METHODS, required=True)
    r.add_argument("--split", choices=("dev", "test", "all"), default="dev")
    r.add_argument("--orders", nargs="+", choices=ORDER_MODES, default=["shuffled"])
    r.add_argument("--seeds", nargs="+", type=int, default=[0])
    r.add_argument("--limit", type=int)
    r.add_argument("--stage1-k", type=int, default=20)
    r.add_argument("--stage2-order", choices=("shuffled", "stage1"), default="shuffled")
    text_args(r)

    p = sub.add_parser("probe")
    p.add_argument("--method", choices=("llama", "llama-pointwise"), default="llama")
    p.add_argument("--n", type=int, default=5)
    text_args(p)

    args = ap.parse_args()
    {"build": cmd_build, "run": cmd_run, "probe": cmd_probe}[args.cmd](args)


if __name__ == "__main__":
    main()
