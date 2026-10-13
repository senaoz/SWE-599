"""Paper figures for the v2 notebooks. Saved as PDF (for LaTeX) and SVG in v2/figures/.

Color carries one job: method *family* (lexical, embedding, cross-encoder, LLM),
in a fixed order that never depends on rank. Benchmarks use the first two slots.
The palette (validated for color-vision deficiency) has two hues under 3:1
contrast on white, so every mark is also labeled in text.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FIG_DIR = Path(__file__).resolve().parents[1] / "v2" / "figures"

SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # blue, orange, aqua, yellow
INK, INK_2, GRID = "#1f1f1e", "#5f5e5a", "#e6e5e0"

FAMILIES = ["Lexical", "Embedding", "Cross-encoder", "LLM"]
FAMILY_COLOR = dict(zip(FAMILIES, SLOTS))
BENCH_COLOR = {"random": SLOTS[0], "concept": SLOTS[1]}

LABELS = {
    "bm25": "BM25", "tfidf": "TF-IDF", "minilm": "MiniLM", "specter2": "SPECTER2",
    "qwen": "Qwen3-Embedding-8B", "embeddinggemma": "EmbeddingGemma", "qwen+minilm": "Qwen3 + MiniLM",
    "bge-reranker": "bge-reranker-base", "llama": "Llama 3.2 3B (listwise)",
    "llama-pointwise": "Llama 3.2 3B (pointwise)", "llama-window": "Llama 3.2 3B (sliding window)", "llama+minilm": "Llama + MiniLM",
}


def label(method: str) -> str:
    if method.startswith("qwen→llama"):
        k = method.split("_k")[-1].split("_")[0] if "_k" in method else "?"
        return f"Qwen3 → Llama (k={k})"
    return LABELS.get(method, method)


def family(method: str) -> str:
    if method in ("bm25", "tfidf"):
        return "Lexical"
    if method == "bge-reranker":
        return "Cross-encoder"
    if method.startswith(("llama", "qwen→llama")):
        return "LLM"
    return "Embedding"


def setup_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
        "axes.edgecolor": INK_2, "axes.labelcolor": INK, "xtick.color": INK_2, "ytick.color": INK,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "lines.linewidth": 2, "lines.markersize": 7,
        "legend.frameon": False, "svg.fonttype": "none", "pdf.fonttype": 42,
    })


def save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "svg"):
        fig.savefig(FIG_DIR / f"{name}.{ext}", bbox_inches="tight")


def _family_legend(ax, fams) -> None:
    handles = [plt.Line2D([], [], marker="o", ls="", color=FAMILY_COLOR[f], label=f) for f in FAMILIES if f in fams]
    ax.legend(handles=handles, loc="lower right", fontsize=8)


# ---------------------------------------------------------------------------
# Data (01, 02)
# ---------------------------------------------------------------------------

def fig_query_years(years: pd.Series):
    counts = years.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(4.2, 2.4))
    ax.bar(counts.index, counts.values, color=SLOTS[0], width=0.6)
    for x, y in zip(counts.index, counts.values):
        ax.text(x, y, str(y), ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_ylabel("Query papers"); ax.set_title("Query papers by publication year")
    ax.grid(axis="x", visible=False)
    return fig


def fig_dataset_overview(datasets: dict):
    """(a) positives per query; (b) topical overlap of candidates with the query, per benchmark."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 2.6), gridspec_kw={"width_ratios": [1.1, 1]})
    ds = next(iter(datasets.values()))
    npos = pd.Series([len(s["positives"]) for s in ds["sets"]]).value_counts().sort_index()
    a.bar(npos.index, npos.values, color=SLOTS[0], width=0.7)
    a.set_xlabel("Positives (cited references) per query"); a.set_ylabel("Queries")
    a.set_title("(a) Pool size: n positives + 2n negatives"); a.grid(axis="x", visible=False)

    rows = []
    for bench, d in datasets.items():
        P = d["papers"]
        top = lambda pid: set(P[pid]["concepts_array"][:5])  # noqa: E731
        for role in ("positives", "negatives"):
            share = np.mean([bool(top(s["pi_id"]) & top(c)) for s in d["sets"] for c in s[role]])
            rows.append((bench, role, share * 100))
    df = pd.DataFrame(rows, columns=["bench", "role", "share"])
    y = {"positives": 1, "negatives": 0}
    for bench, g in df.groupby("bench", sort=False):
        for _, r in g.iterrows():
            yy = y[r["role"]] + (0.12 if bench == "random" else -0.12)
            b.plot([0, r["share"]], [yy, yy], color=BENCH_COLOR[bench], lw=2, solid_capstyle="round")
            b.plot(r["share"], yy, "o", color=BENCH_COLOR[bench])
            b.text(r["share"] + 2, yy, f"{r['share']:.0f}%", va="center", fontsize=8, color=INK)
    b.set_yticks([0, 1], ["Negatives", "Positives"]); b.set_xlim(0, 110)
    b.set_xlabel("% sharing a top-5 OpenAlex concept with the query")
    b.set_title("(b) Topical overlap with the query")
    b.legend(handles=[plt.Line2D([], [], color=c, marker="o", label=k) for k, c in BENCH_COLOR.items()],
             loc="center right", fontsize=8, title="Benchmark", title_fontsize=8)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Dev tuning (03)
# ---------------------------------------------------------------------------

FIELD_NAMES = {"t": "Title", "ta": "Title + abstract", "tac": "Title + abstract + concepts"}


def tag_label(tag: str) -> str:
    fields, max_chars, _ = tag.split("_")
    return FIELD_NAMES.get(fields, fields) + ("" if fields == "t" else f" ({max_chars} chars)")


def fig_dev_tuning(dev: pd.DataFrame):
    """R-precision on dev per method, one panel per benchmark, one marker per text config."""
    tags = sorted(dev["text_tag"].unique(), key=len)
    markers = ["o", "s", "D", "^"]
    benches = [b for b in BENCH_COLOR if b in set(dev["bench"])]
    fig, axes = plt.subplots(1, len(benches), figsize=(3.8 * len(benches), 0.32 * dev["method"].nunique() + 1.6),
                             sharey=True)
    axes = np.atleast_1d(axes)
    methods = dev.groupby("method")["rprec"].mean().sort_values().index.tolist()
    for ax, bench in zip(axes, benches):
        d = dev[dev["bench"] == bench]
        for i, tag in enumerate(tags):
            t = d[d["text_tag"] == tag].set_index("method").reindex(methods)
            ax.plot(t["rprec"], range(len(methods)), markers[i % 4], ls="", color=SLOTS[0] if i == 0 else INK_2,
                    mfc=SLOTS[0] if i == 0 else "white", label=tag_label(tag))
        ax.set_title(f"{bench.capitalize()} benchmark (dev)"); ax.set_xlabel("R-precision %")
    axes[0].set_yticks(range(len(methods)), [label(m) for m in methods])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(tags), fontsize=8, title="Candidate text",
               title_fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    return fig


def fig_stage1_k(two_stage: pd.DataFrame, baseline: dict):
    """Two-stage R-precision against stage-1 k, with stage 1 alone (Qwen3) as a reference line."""
    fig, ax = plt.subplots(figsize=(4.4, 2.7))
    for bench, g in two_stage.groupby("bench", sort=False):
        g = g.sort_values("k")
        c = BENCH_COLOR[bench]
        ax.plot(g["k"], g["rprec"], "-o", color=c, label=f"Qwen3 → Llama ({bench})")
        ax.hlines(baseline[bench], g["k"].min(), g["k"].max(), color=c, ls="--", lw=1)
        ax.text(g["k"].max() + 0.8, baseline[bench], f"Qwen3 alone\n({bench})", va="center", fontsize=7, color=INK_2)
    ax.set_xticks(sorted(two_stage["k"].unique())); ax.set_xlabel("Candidates passed to Llama (stage-1 k)")
    ax.set_ylabel("R-precision % (dev)"); ax.set_title("Reranking more candidates hurts")
    ax.set_xlim(right=two_stage["k"].max() + 9)
    ax.legend(fontsize=7, loc="center right")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Results (05)
# ---------------------------------------------------------------------------

def fig_forest(table: pd.DataFrame, bench: str, metric: str = "rprec"):
    """Mean with 95% bootstrap CI per method, colored by family, with the chance level."""
    is_chance = table["method"].str.startswith("chance")
    chance = table.loc[is_chance, metric].iloc[0] if is_chance.any() else None
    m = table[~is_chance].sort_values(metric)
    fig, ax = plt.subplots(figsize=(6.2, 0.3 * len(m) + 1.1))
    for i, (_, r) in enumerate(m.iterrows()):
        c = FAMILY_COLOR[family(r["method"])]
        ax.plot([r[f"{metric}_lo"], r[f"{metric}_hi"]], [i, i], color=c, lw=2, solid_capstyle="round")
        ax.plot(r[metric], i, "o", color=c, mec="white", mew=1.5)
        ax.text(r[f"{metric}_hi"] + (1 if metric == "rprec" else 0.01), i,
                f"{r[metric]:.1f}" if metric == "rprec" else f"{r[metric]:.3f}", va="center", fontsize=8, color=INK)
    if chance is not None:
        ax.axvline(chance, color=INK_2, ls="--", lw=1)
        ax.text(chance, len(m) - 0.4, " chance", color=INK_2, fontsize=8, va="bottom")
    ax.set_yticks(range(len(m)), [label(x) for x in m["method"]])
    ax.set_xlabel({"rprec": "R-precision % (95% bootstrap CI)", "mrr": "MRR (95% bootstrap CI)"}[metric])
    ax.set_title(f"{bench.capitalize()} benchmark, test queries"); ax.grid(axis="y", visible=False)
    _family_legend(ax, {family(x) for x in m["method"]})
    fig.tight_layout()
    return fig


def fig_bench_compare(tables: dict, metric: str = "rprec"):
    """Dumbbell: each method's score on the random vs concept benchmark."""
    t = {b: v["methods"].set_index("method")[metric] for b, v in tables.items()}
    common = [m for m in t["concept"].index if m in t["random"].index and not m.startswith("chance")]
    order = sorted(common, key=lambda m: t["concept"][m])
    fig, ax = plt.subplots(figsize=(6.2, 0.3 * len(order) + 1.1))
    for i, m in enumerate(order):
        ax.plot([t["concept"][m], t["random"][m]], [i, i], color=GRID, lw=3, zorder=1)
        for b in ("random", "concept"):
            ax.plot(t[b][m], i, "o", color=BENCH_COLOR[b], zorder=2, mec="white", mew=1.2)
    ax.set_yticks(range(len(order)), [label(m) for m in order])
    ax.set_xlabel("R-precision %" if metric == "rprec" else metric.upper())
    ax.set_title("Harder negatives: random vs concept-matched"); ax.grid(axis="y", visible=False)
    ax.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=c, label=b) for b, c in BENCH_COLOR.items()],
              loc="lower right", fontsize=8, title="Benchmark", title_fontsize=8)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Analyses (06)
# ---------------------------------------------------------------------------

def fig_position_bias(tables: dict):
    """Listwise Llama under three input orders, per benchmark."""
    orders = ["original", "shuffled", "reversed"]
    names = {"original": "Positives first (v1)", "shuffled": "Shuffled (v2)", "reversed": "Positives last"}
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.4), sharey=True)
    for ax, metric, xl in zip(axes, ("mrr", "rprec"), ("MRR", "R-precision %")):
        for j, (bench, t) in enumerate(tables.items()):
            t = t.set_index("order").reindex(orders)
            y = np.arange(len(orders)) + (0.12 if j == 0 else -0.12)
            ax.plot(t[metric], y, "o", color=BENCH_COLOR[bench], label=bench)
            for yy, v in zip(y, t[metric]):
                ax.annotate(f"{v:.2f}" if metric == "mrr" else f"{v:.0f}", (v, yy), xytext=(-7, 0),
                            textcoords="offset points", ha="right", va="center", fontsize=7, color=INK)
        ax.set_xlabel(xl)
        lo = min(t[metric].min() for t in tables.values())
        ax.set_xlim(left=lo - (0.12 if metric == "mrr" else 10))
    axes[0].set_yticks(range(len(orders)), [names[o] for o in orders]); axes[0].invert_yaxis()
    axes[1].legend(title="Benchmark", fontsize=8, title_fontsize=8, loc="lower right")
    fig.suptitle("Listwise Llama 3.2 3B: effect of candidate order", fontsize=10)
    fig.tight_layout()
    return fig


def fig_stage1_recall(recalls: dict, k_used: int | None = None):
    """Recall of true references in each first-stage method's top k; one panel per benchmark.

    recalls: {bench: {method: stage1_recall() summary}}.
    """
    styles = {"qwen": (FAMILY_COLOR["Embedding"], "-", "Qwen3-Embedding-8B"),
              "bm25": (FAMILY_COLOR["Lexical"], "-", "BM25"),
              "bm25+qwen (RRF)": (SLOTS[2], "--", "BM25 + Qwen3 (RRF)")}
    benches = [b for b in BENCH_COLOR if b in recalls]
    fig, axes = plt.subplots(1, len(benches), figsize=(3.7 * len(benches), 2.7), sharey=True)
    for ax, bench in zip(np.atleast_1d(axes), benches):
        for method, summary in recalls[bench].items():
            color, ls, name = styles.get(method, (INK_2, "-", method))
            ks = [int(i.split("@")[1]) for i in summary.index]
            ax.plot(ks, summary["mean"] * 100, ls, marker="o", color=color, label=name)
        if k_used:
            ax.axvline(k_used, color=INK_2, ls=":", lw=1)
            ax.text(k_used + 0.8, 8, f"two-stage k = {k_used}", fontsize=7, color=INK_2)
        ax.set_xticks(ks); ax.set_xlabel("k (stage-1 cut-off)"); ax.set_ylim(0, 105)
        ax.set_title(f"{bench.capitalize()} benchmark")
    np.atleast_1d(axes)[0].set_ylabel("Mean recall of cited references %")
    np.atleast_1d(axes)[-1].legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    return fig
