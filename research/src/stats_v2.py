"""Statistics and analyses for the v2 benchmark (used by v2/05_stats and v2/06_analysis).

Same tests as v1 (research/v1/stats/significance.py): percentile bootstrap CIs over
queries and paired Wilcoxon signed-rank tests with Holm correction. For methods
run with several shuffle seeds, each query's metric is first averaged over seeds;
the spread across seeds is reported separately.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

N_BOOT = 10_000
SEED = 42
METRICS = ("mrr", "rprec", "ndcg", "ap")


def boot_ci(x: np.ndarray, rng: np.random.Generator, n_boot: int = N_BOOT) -> tuple[float, float]:
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    lo, hi = np.percentile(x[idx].mean(axis=1), [2.5, 97.5])
    return float(lo), float(hi)


def holm(pvals: list[float]) -> list[float]:
    order = np.argsort(pvals)
    m = len(pvals)
    adj, running = np.empty(m), 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj.tolist()


def per_query(df: pd.DataFrame, order: str = "shuffled") -> pd.DataFrame:
    """Seed-averaged metric per (method, query) for one candidate-order condition."""
    d = df[df["order"] == order]
    return d.groupby(["method", "pi_id"])[list(METRICS)].mean().reset_index()


def seed_spread(df: pd.DataFrame, order: str = "shuffled") -> pd.DataFrame:
    """Mean metric per (method, seed), then mean ± sd and min–max across seeds."""
    by_seed = df[df["order"] == order].groupby(["method", "seed"])[list(METRICS)].mean()
    g = by_seed.groupby("method")
    out = pd.DataFrame({"seeds": g.size()})
    for m in ("mrr", "rprec"):
        out[f"{m}_sd"] = g[m].std(ddof=1)
        out[f"{m}_min"] = g[m].min()
        out[f"{m}_max"] = g[m].max()
    return out.round(4).reset_index()


def method_table(pq: pd.DataFrame, chance: dict | None = None) -> pd.DataFrame:
    """Mean and 95% bootstrap CI per method over the queries every method covers."""
    common = set.intersection(*(set(g["pi_id"]) for _, g in pq.groupby("method")))
    rng = np.random.default_rng(SEED)
    rows = []
    for method, g in pq[pq["pi_id"].isin(common)].groupby("method"):
        g = g.sort_values("pi_id")
        row = {"method": method, "queries": len(g)}
        for m in METRICS:
            x = g[m].to_numpy()
            lo, hi = boot_ci(x, rng)
            row[m], row[f"{m}_lo"], row[f"{m}_hi"] = x.mean(), lo, hi
        rows.append(row)
    out = pd.DataFrame(rows).sort_values("rprec", ascending=False)
    if chance:
        out = pd.concat([out, pd.DataFrame([{"method": "chance (random ranking)", **chance}])])
    return out.round(4).reset_index(drop=True)


def pairwise_tests(pq: pd.DataFrame, pairs: list[tuple[str, str]],
                   metrics=("mrr", "rprec")) -> pd.DataFrame:
    """Paired Wilcoxon signed-rank tests, Holm-corrected across all rows."""
    wide = {m: pq.pivot(index="pi_id", columns="method", values=m) for m in metrics}
    rows = []
    for a, b in pairs:
        for m in metrics:
            both = wide[m][[a, b]].dropna()
            x, y = both[a].to_numpy(), both[b].to_numpy()
            p = wilcoxon(x, y).pvalue if np.any(x != y) else 1.0
            rows.append({"a": a, "b": b, "metric": m, "queries": len(both),
                         "mean_diff": x.mean() - y.mean(), "p": p})
    out = pd.DataFrame(rows)
    out["p_holm"] = holm(out["p"].tolist())
    return out.round({"mean_diff": 4, "p": 6, "p_holm": 6})


def chance_levels(sets: list[dict]) -> dict:
    """Expected metrics under a uniformly random ranking, averaged over queries."""
    from math import comb
    mrr, rprec = [], []
    for s in sets:
        n, N = len(s["positives"]), len(s["positives"]) + len(s["negatives"])
        total = comb(N, n)
        mrr.append(sum(comb(N - r, n - 1) / total / r for r in range(1, N - n + 2)))
        rprec.append(100 * n / N)
    return {"mrr": float(np.mean(mrr)), "rprec": float(np.mean(rprec))}


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------

def position_bias(df: pd.DataFrame, method: str) -> pd.DataFrame:
    """Same queries and seeds, three input orders: v1's positives-first, shuffled, reversed."""
    d = df[df["method"] == method]
    common = set.intersection(*(set(g["pi_id"]) for _, g in d.groupby("order")))
    d = d[d["pi_id"].isin(common)]
    return (d.groupby("order")[["mrr", "rprec", "top1"]].mean()
            .assign(queries=len(common)).round(4).reset_index())


def stage1_recall(df: pd.DataFrame, method: str = "qwen", ks=(5, 10, 20, 50)) -> pd.DataFrame:
    """Share of each query's references that stage 1 keeps in its top k."""
    d = df[(df["method"] == method) & (df["order"] == "shuffled")]
    cols = [f"recall@{k}" for k in ks]
    out = d.groupby("pi_id")[cols].mean()
    summary = out.agg(["mean", "min"]).T
    summary["queries_full_recall"] = (out == 1.0).sum()
    summary["queries"] = len(out)
    return summary.round(4)


def contamination_split(pq: pd.DataFrame, dates: dict[str, str], cutoff: str,
                        llm: str, baseline: str, metric: str = "rprec") -> pd.DataFrame:
    """LLM gain over a baseline for queries published before vs after a knowledge cutoff."""
    wide = pq.pivot(index="pi_id", columns="method", values=metric)[[llm, baseline]].dropna()
    wide["gain"] = wide[llm] - wide[baseline]
    wide["period"] = ["after cutoff" if dates[q] > cutoff else "before cutoff" for q in wide.index]
    return (wide.groupby("period")
            .agg(queries=("gain", "size"), llm=(llm, "mean"), baseline=(baseline, "mean"),
                 gain=("gain", "mean"))
            .round(4).reset_index())
