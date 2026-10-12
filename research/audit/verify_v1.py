"""Reproduce the v1 audit findings from the saved week3 rankings.

Reads research/v1/results/rankings_*.json (read-only). Each file stores,
per query, only the top-n_positives candidate indices; in v1 the candidate list
was positives + negatives, so index < n_positives means "positive".

Usage (from the repository root):
    python research/audit/verify_v1.py
"""
from __future__ import annotations

import json
from math import comb
from pathlib import Path

import numpy as np

WEEK3 = Path(__file__).resolve().parents[1] / "v1" / "results"
STAGE1_K = 20  # top-k kept by stage 1 in the v1 two-stage method


def load() -> dict[str, list[dict]]:
    return {p.stem.removeprefix("rankings_"): json.loads(p.read_text())
            for p in sorted(WEEK3.glob("rankings_*.json"))}


def expected_random_rr(n_pos: int, n_cand: int) -> float:
    """E[1/rank of first positive] under a uniformly random ranking."""
    total = comb(n_cand, n_pos)
    return sum(comb(n_cand - r, n_pos - 1) / total / r for r in range(1, n_cand - n_pos + 2))


def is_fallback(r: dict) -> bool:
    """v1 LLM failure signature: every parsed candidate scores (n - rank) / n > 0,
    so an all-zero top-n means the model output was not used."""
    return all(s == 0 for s in r["ranked_scores"])


def mean(xs) -> float:
    xs = list(xs)
    return float(np.mean(xs)) if xs else float("nan")


def main() -> None:
    data = load()
    ref = data["llama"]
    ids = [r["pi_id"] for r in ref]
    assert all([r["pi_id"] for r in d] == ids for d in data.values()), "query order differs"
    n_q = len(ref)

    # Assumes the full 2n negatives (3n candidates); the JSON files do not store pool size.
    chance = mean(expected_random_rr(r["n_positives"], 3 * r["n_positives"]) for r in ref)
    print(f"Queries: {n_q}; n_positives range {min(r['n_positives'] for r in ref)}"
          f"-{max(r['n_positives'] for r in ref)}")
    print(f"Chance MRR (random ranking, 3n candidates): {chance:.3f}")
    print("Chance R-precision (share of top-n that are positives): 33.3%\n")

    print("## F2/F3/F6 — scores vs chance, top-1 candidate index, fallback signature")
    print(f"{'method':16s} {'MRR':>6s} {'R-prec':>6s} {'top1=0':>7s} {'top1=1':>7s} {'top1=2':>7s} "
          f"{'fallback':>8s} {'negs in top-n: mean rel. position':>34s}")
    for m, d in data.items():
        top1 = [r["ranked_ids"][0] for r in d]
        # Among negatives a method placed in its top-n, where did they sit in the
        # original negative block? 0 = first negative, 1 = last. Random ≈ 0.5.
        neg_pos = [(i - r["n_positives"]) / (2 * r["n_positives"] - 1)
                   for r in d for i in r["ranked_ids"] if i >= r["n_positives"]]
        print(f"{m:16s} {mean(r['mrr'] for r in d):6.3f} {mean(r['hit_rate'] for r in d):6.1f} {top1.count(0):7d} {top1.count(1):7d} "
              f"{top1.count(2):7d} {sum(map(is_fallback, d)):8d} {mean(neg_pos):34.3f}")

    print("\n## F3 — Llama fallback queries")
    fb = [i for i, r in enumerate(ref) if is_fallback(r)]
    for i in fb:
        print(f"  {ref[i]['pi_id']}  n={ref[i]['n_positives']}  "
              f"llama MRR={ref[i]['mrr']}  qwen→llama fallback={is_fallback(data['qwen→llama'][i])}")
    fb2 = [i for i, r in enumerate(data["qwen→llama"]) if is_fallback(r)]
    print(f"  qwen→llama fallback queries: {[ref[i]['pi_id'] for i in fb2]}")
    keep = [i for i in range(n_q) if i not in fb]
    print(f"  Llama MRR all queries: {mean(ref[i]['mrr'] for i in range(n_q)):.3f}; "
          f"excluding {len(fb)} fallbacks: {mean(ref[i]['mrr'] for i in keep):.3f}")

    print("\n## F5 — two-stage on pools that stage 1 cannot truncate (3n <= "
          f"{STAGE1_K})")
    small = [i for i, r in enumerate(ref) if 3 * r["n_positives"] <= STAGE1_K]
    large = [i for i in range(n_q) if i not in small]
    for label, sub in (("pool <= 20", small), ("pool > 20", large)):
        row = "  ".join(f"{m}={mean(data[m][i]['mrr'] for i in sub):.3f}"
                        for m in ("llama", "qwen→llama", "qwen"))
        print(f"  {label:10s} (n={len(sub):3d}): {row}")


if __name__ == "__main__":
    main()
