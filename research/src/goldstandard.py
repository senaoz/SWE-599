"""LLM and lexical methods on the Stelmakh et al. gold standard (v2/17_llm_goldstandard.ipynb).

The label is a researcher's self-rated expertise in reviewing a paper, so the prompts ask
about reviewing expertise, not citation; their structure is the v2 one (numbered list and
JSON array; 0–10 integer; yes/no for Qwen3-Reranker). Every LLM call is cached in a JSONL
file, so an interrupted run resumes and the notebook only reads the caches.

    .venv/bin/python -m src.goldstandard listwise|pointwise|reranker GOLDSTANDARD_DIR
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SAMPLES = range(1, 11)
LISTWISE_SEEDS = range(1, 6)          # seed s uses profile sample d_20_s
ORDERS = ("shuffled", "best_first", "worst_first")
CAND_CHARS, QUERY_CHARS = 600, 1500   # as in the v2 benchmark

LISTWISE_EXPERTISE = (
    "You are matching papers to reviewers.\n\n"
    "Papers written by the researcher:\n{query}\n\n"
    "Candidate papers:\n{candidates}\n\n"
    "Rank all {n} candidate papers from the one this researcher is most qualified to review "
    "to the one they are least qualified to review. Respond ONLY with a JSON array of the "
    "candidate numbers, each number exactly once, most qualified first."
)
POINTWISE_EXPERTISE = (
    "You are matching papers to reviewers.\n\n"
    "Papers written by the researcher:\n{query}\n\n"
    "Candidate paper:\n{candidate}\n\n"
    "On a scale from 0 to 10, how qualified is this researcher to review the candidate paper? "
    "Respond ONLY with a single integer from 0 to 10."
)
RERANKER_EXPERTISE = ("Given the title and abstract of a paper written by a researcher, "
                      "retrieve papers that this researcher is qualified to review")


def rng_for(*parts) -> np.random.Generator:
    """Seeded from sha256 (never hash(), which is salted per process)."""
    return np.random.default_rng(int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16], 16))


def load(G: Path) -> dict:
    """refs: reviewer -> {paper: rating}; text/titles: paper -> str; profiles: sample -> reviewer -> [ids]."""
    ev = pd.read_csv(G / "data" / "evaluations.csv", sep="\t")
    refs = {}
    for _, r in ev.iterrows():
        refs[str(r.ParticipantID)] = {r[f"Paper{i}"]: float(r[f"Expertise{i}"]) for i in range(1, 11)
                                      if isinstance(r[f"Paper{i}"], str) and not pd.isna(r[f"Expertise{i}"])}
    text, titles, profiles = {}, {}, {}
    add = lambda pid, c: (text.setdefault(pid, f"{c['title']} {c.get('abstract') or ''}".strip()),
                          titles.setdefault(pid, c["title"]))
    for i in SAMPLES:
        D = G / "evaluation_datasets" / f"d_20_{i}"
        for pid, s in json.load(open(D / "submissions.json")).items():
            add(pid, s["content"])
        profiles[i] = {}
        for rv in sorted(refs):
            rows = [json.loads(l) for l in open(D / "archives" / f"~{rv}.jsonl")]
            profiles[i][rv] = [x["id"] for x in rows]
            for x in rows:
                add(x["id"], x["content"])
    return {"refs": refs, "text": text, "titles": titles, "profiles": profiles}


def profile_query(data: dict, i: int, rv: str) -> str:
    return "\n".join(f"- {data['titles'][q]}" for q in data["profiles"][i][rv])


# ---------------------------------------------------------------------------
# Lexical: each profile paper is a query, rated papers are documents, max over the profile
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(s: str) -> list[str]:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    return [t for t in _TOKEN.findall(s.lower()) if t not in ENGLISH_STOP_WORDS]


def lexical_preds(data: dict, method: str) -> list[dict]:
    """IDF is fitted on every text of the profile sample (rated and profile papers)."""
    from rank_bm25 import BM25Okapi
    from sklearn.feature_extraction.text import TfidfVectorizer
    refs, text = data["refs"], data["text"]
    out = []
    for i in SAMPLES:
        prof = data["profiles"][i]
        ids = sorted({p for rv in refs for p in refs[rv]} | {q for v in prof.values() for q in v})
        pos = {p: k for k, p in enumerate(ids)}
        if method == "bm25":
            bm = BM25Okapi([tokens(text[p]) for p in ids])
            sim = lambda q, ps: bm.get_batch_scores(tokens(text[q]), [pos[p] for p in ps])
        else:
            vec = TfidfVectorizer(tokenizer=tokens, lowercase=False, token_pattern=None)
            X = vec.fit_transform([text[p] for p in ids])
            sim = lambda q, ps: (X[[pos[p] for p in ps]] @ X[pos[q]].T).toarray().ravel()
        d = {}
        for rv in refs:
            rated = list(refs[rv])
            S = np.array([sim(q, rated) for q in prof[rv]])
            d[rv] = dict(zip(rated, S.max(axis=0).astype(float).tolist()))
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Listwise Llama under three orders
# ---------------------------------------------------------------------------

def shown_order(ratings: dict, order: str, seed: int, rv: str) -> list[str]:
    """Papers in the order shown. Ties in best/worst-first are broken by a seeded shuffle."""
    papers = sorted(ratings)
    perm = [papers[k] for k in rng_for("order", order, seed, rv).permutation(len(papers))]
    if order == "shuffled":
        return perm
    sign = -1 if order == "best_first" else 1
    return sorted(perm, key=lambda p: sign * ratings[p])   # stable: ties keep the shuffle


def listwise_cache(root: Path, order: str, seed: int) -> Path:
    return root / f"listwise_{order}_seed{seed}.jsonl"


def run_listwise(data: dict, root: Path, orders=ORDERS, seeds=LISTWISE_SEEDS) -> int:
    from src.rankers_v2 import listwise_rank
    refs, text = data["refs"], data["text"]
    new = 0
    for seed in seeds:
        for order in orders:
            path = listwise_cache(root, order, seed)
            done = {json.loads(l)["reviewer"] for l in open(path)} if path.exists() else set()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a") as f:
                for rv in sorted(refs):
                    if rv in done:
                        continue
                    shown = shown_order(refs[rv], order, seed, rv)
                    res = listwise_rank(profile_query(data, seed, rv), [text[p][:CAND_CHARS] for p in shown],
                                        rng_for("fallback", order, seed, rv), seed=seed, template=LISTWISE_EXPERTISE)
                    f.write(json.dumps({"reviewer": rv, "order": order, "seed": seed, "sample": seed, "shown": shown,
                                        "ranked": [shown[k] for k in res["order"]], "status": res["status"],
                                        "n_ranked": res["n_ranked"], "prompt_tokens": res["prompt_tokens"],
                                        "raw": res["raw"]}) + "\n")
                    f.flush()
                    new += 1
                    print(f"listwise {order} seed {seed} {rv}: {res['status']}", flush=True)
    return new


def read_listwise(root: Path, order: str, seed: int) -> list[dict]:
    with listwise_cache(root, order, seed).open() as f:
        return [json.loads(l) for l in f]


# ---------------------------------------------------------------------------
# Pointwise: Llama (profile titles + candidate) and Qwen3-Reranker (one profile paper per query)
# ---------------------------------------------------------------------------

def llama_cache(root: Path):
    from src.rerank import PointwiseCache, llama_pointwise
    return PointwiseCache(root / "pointwise_llama.jsonl",
                          scorer=lambda q, texts: llama_pointwise(q, texts, template=POINTWISE_EXPERTISE))


def run_llama(data: dict, root: Path, samples=SAMPLES) -> int:
    cache, new = llama_cache(root), 0
    for i in samples:
        for rv in sorted(data["refs"]):
            new += cache.ensure(f"{rv}|d_20_{i}", profile_query(data, i, rv), sorted(data["refs"][rv]),
                                lambda p: data["text"][p][:CAND_CHARS])
        print(f"pointwise llama d_20_{i}: {new} new calls so far", flush=True)
    return new


def reranker_pairs(data: dict) -> dict[str, list[str]]:
    """Profile paper -> rated papers to score, over all samples (profiles overlap across samples)."""
    pairs: dict[str, set] = {}
    for i in SAMPLES:
        for rv, prof in data["profiles"][i].items():
            for q in prof:
                pairs.setdefault(q, set()).update(data["refs"][rv])
    return {q: sorted(v) for q, v in sorted(pairs.items())}


def reranker_cache(root: Path, scorer=None):
    from src.rerank import PointwiseCache
    return PointwiseCache(root / "pointwise_qwen3_reranker.jsonl", scorer=scorer)


def run_reranker(data: dict, root: Path, batch_size: int = 8) -> int:
    from src.rerank import Qwen3Reranker
    cache = reranker_cache(root, Qwen3Reranker(instruction=RERANKER_EXPERTISE, batch_size=batch_size))
    new = 0
    for k, (q, docs) in enumerate(reranker_pairs(data).items()):
        new += cache.ensure(q, data["text"][q][:QUERY_CHARS], docs, lambda p: data["text"][p][:CAND_CHARS])
        if k % 50 == 0:
            print(f"reranker query {k}: {new} new pairs", flush=True)
    return new


def max_preds(data: dict, cache) -> list[dict]:
    """Max over profile papers of a reranker score cached per (profile paper, rated paper)."""
    out = []
    for i in SAMPLES:
        out.append({rv: {p: max(cache.get(q, [p])[0] for q in data["profiles"][i][rv]) for p in rated}
                    for rv, rated in data["refs"].items()})
    return out


if __name__ == "__main__":
    what, G = sys.argv[1], Path(sys.argv[2])
    ROOT = Path(__file__).resolve().parents[1] / "data" / "v2" / "goldstandard_llm"
    data = load(G)
    if what == "listwise":
        print("new calls:", run_listwise(data, ROOT))
    elif what == "pointwise":
        samples = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else SAMPLES
        print("new calls:", run_llama(data, ROOT, samples))
    elif what == "reranker":
        print("new pairs:", run_reranker(data, ROOT))
    else:
        raise SystemExit(f"unknown run: {what}")
