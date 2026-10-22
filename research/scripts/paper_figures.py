"""Figures for paper/main.tex and the README that combine several notebooks' results.

Position bias: listwise Llama 3.2 3B and 3.1 8B under three candidate orders. Citation panels:
test split, seed 0, R-precision with 95% bootstrap CIs over queries (as in v2/05_stats). Human
panel: v2/goldstandard/17_results.csv (seeds 1-5). Writes v2/figures/position_bias_3b_8b.{pdf,svg,csv}.

Figure 3: each method's citation score (R-precision, random negatives, test split; same
seed averaging and bootstrap as v2/05_stats) against its human-label loss (Stelmakh et al.
gold standard; v2/goldstandard/14_results.csv and 17_results.csv). Writes
v2/figures/fig3_label_agreement.{pdf,svg} and the plotted values to a CSV beside them.

    .venv/bin/python -m scripts.paper_figures
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from src.figures import FAMILY_COLOR, FIG_DIR, INK, INK_2, SLOTS, save, setup_style
from src.pipeline_v2 import load_runs
from src.stats_v2 import N_BOOT, SEED, boot_ci, method_table, per_query

V2 = Path(__file__).resolve().parents[1] / "v2"
GS = V2 / "goldstandard"

# citation run name -> (gold-standard name, label, family)
METHODS = {
    "qwen": ("qwen", "Qwen3-Embedding-8B", "Embedding"),
    "specter2": ("specter2", "SPECTER2", "Embedding"),
    "minilm": ("minilm", "MiniLM", "Embedding"),
    "tfidf": ("tfidf", "TF-IDF", "Lexical"),
    "bm25": ("bm25", "BM25", "Lexical"),
    "llama-pointwise": ("pointwise_llama", "Llama 3B pointwise", "LLM"),
    "llama": ("listwise_shuffled", "Llama 3B listwise", "LLM"),
    "llama8b": ("listwise8b_shuffled", "Llama 8B listwise", "LLM"),
}
# label placement, chosen by eye: the three embeddings sit within a few points of each
# other, so their labels go to the empty upper left with leader lines
LEADER = {"qwen": (72, 0.183), "specter2": (72, 0.203), "minilm": (72, 0.223)}
OFFSETS = {"tfidf": (6, 4, "left"), "bm25": (-6, -8, "right"),
           "llama-pointwise": (6, -6, "left"), "llama": (-4, 11, "left"),
           "llama8b": (-7, 0, "right")}


def citation_scores() -> pd.DataFrame:
    """R-precision mean and CI per method, computed exactly as in v2/05_stats."""
    C = json.loads((V2 / "config.json").read_text())
    tag = f"{C['fields']}_{C['max_chars']}_{C['query_max_chars']}"
    df = load_runs("random", tag, split="test")
    is8 = df["method"].str.contains("llama8b")
    # 05_stats predates the 8B runs; score them apart so the other CIs stay exactly as in 05
    table = method_table(per_query(df[~is8])).set_index("method")
    table8 = method_table(per_query(df[is8 & (df["method"] == "llama8b")])).set_index("method")
    return pd.concat([table, table8])


def human_scores() -> pd.DataFrame:
    res = pd.concat([pd.read_csv(GS / "14_results.csv"), pd.read_csv(GS / "17_results.csv")])
    return res.drop_duplicates("method").set_index("method")


def fig_label_agreement() -> None:
    cit, hum = citation_scores(), human_scores()
    rows = []
    for m, (g, lab, fam) in METHODS.items():
        rows.append({"method": m, "label": lab, "family": fam,
                     "rprec": cit.loc[m, "rprec"], "rprec_lo": cit.loc[m, "rprec_lo"], "rprec_hi": cit.loc[m, "rprec_hi"],
                     "loss": hum.loc[g, "loss"], "loss_lo": hum.loc[g, "lo"], "loss_hi": hum.loc[g, "hi"]})
    d = pd.DataFrame(rows)
    tau = kendalltau(d["rprec"], -d["loss"]).statistic
    d.to_csv(FIG_DIR / "fig3_label_agreement.csv", index=False, float_format="%.4f")

    setup_style()
    fig, ax = plt.subplots(figsize=(3.3, 2.6))
    for r in d.itertuples():
        c = FAMILY_COLOR[r.family]
        ax.errorbar(r.rprec, r.loss, xerr=[[r.rprec - r.rprec_lo], [r.rprec_hi - r.rprec]],
                    yerr=[[r.loss - r.loss_lo], [r.loss_hi - r.loss]],
                    fmt="none", ecolor=c, elinewidth=0.8, alpha=0.55, capsize=0)
        ax.plot(r.rprec, r.loss, "o", color=c, mec="white", mew=1.2, ms=6.5, zorder=3)
        if r.method in LEADER:
            ax.annotate(r.label, (r.rprec, r.loss), xytext=LEADER[r.method], textcoords="data",
                        ha="right", va="center", fontsize=7, color=INK,
                        arrowprops=dict(arrowstyle="-", color=INK_2, lw=0.5, shrinkA=2, shrinkB=4))
        else:
            dx, dy, ha = OFFSETS[r.method]
            ax.annotate(r.label, (r.rprec, r.loss), xytext=(dx, dy), textcoords="offset points",
                        ha=ha, va="center", fontsize=7, color=INK)
    ax.axhline(0.5, color=INK_2, lw=0.8, ls=":")
    ax.text(36, 0.5, "constant ranking", fontsize=6.5, color=INK_2, va="bottom")
    ax.axvline(100 / 3, color=INK_2, lw=0.8, ls=":")
    ax.text(34.5, 0.30, "random ranking", fontsize=6.5, color=INK_2, va="center")
    ax.set_xlim(32, 92)
    ax.set_ylim(0.52, 0.17)  # inverted: better is up
    ax.set_xlabel("Citation labels: R-precision % (higher is better)", fontsize=8)
    ax.set_ylabel("Human labels: $\\tau$ loss (lower is better)", fontsize=8)
    ax.tick_params(labelsize=7)
    handles = [plt.Line2D([], [], marker="o", ls="", color=FAMILY_COLOR[f], label=f)
               for f in ("Lexical", "Embedding", "LLM")]
    ax.legend(handles=handles, loc="lower right", fontsize=7, handletextpad=0.2)
    fig.tight_layout()
    save(fig, "fig3_label_agreement")
    print(d[["method", "rprec", "rprec_lo", "rprec_hi", "loss", "loss_lo", "loss_hi"]].round(3).to_string(index=False))
    print(f"Kendall tau between the two orderings (n={len(d)}): {tau:.3f}")


ORDERS = {"original": "Cited first", "shuffled": "Shuffled", "reversed": "Cited last"}
MODELS = {"llama": ("Llama 3.2 3B", SLOTS[0]), "llama8b": ("Llama 3.1 8B", SLOTS[1])}


def fig_position_bias_models() -> None:
    C = json.loads((V2 / "config.json").read_text())
    tag = f"{C['fields']}_{C['max_chars']}_{C['query_max_chars']}"
    rng = np.random.default_rng(SEED)
    rows, ref = [], {}
    for bench in ("random", "concept"):
        df = load_runs(bench, tag, split="test")
        df = df[df["seed"] == 0]
        ref[bench] = df[(df["method"] == "qwen") & (df["order"] == "shuffled")]["rprec"].mean()
        for m in MODELS:
            for o in ORDERS:
                x = df[(df["method"] == m) & (df["order"] == o)].sort_values("pi_id")["rprec"].to_numpy()
                lo, hi = boot_ci(x, rng, N_BOOT)
                rows.append({"bench": bench, "model": m, "order": o, "queries": len(x),
                             "rprec": x.mean(), "lo": lo, "hi": hi})
    assert all(r["queries"] == 118 for r in rows), rows

    hum = pd.read_csv(GS / "17_results.csv").set_index("method")
    for m, pre in (("llama", "listwise"), ("llama8b", "listwise8b")):
        for o, go in zip(ORDERS, ("best_first", "shuffled", "worst_first")):
            r = hum.loc[f"{pre}_{go}"]
            rows.append({"bench": "human", "model": m, "order": o, "queries": 58,
                         "rprec": r["loss"], "lo": r["lo"], "hi": r["hi"]})
    ref["human"] = hum.loc["listwise8b_shuffled", "qwen on same samples"]
    d = pd.DataFrame(rows)
    d.to_csv(FIG_DIR / "position_bias_3b_8b.csv", index=False, float_format="%.4f")

    setup_style()
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.4))
    xs = np.arange(len(ORDERS))
    panels = {"random": ("Citation labels, random negatives", "{:.0f}"),
              "concept": ("Citation labels, concept negatives", "{:.0f}"),
              "human": ("Human labels (Stelmakh et al.)", "{:.2f}")}
    for ax, (bench, (title, fmt)) in zip(axes, panels.items()):
        human = bench == "human"
        ax.axhline(ref[bench], color=INK_2, lw=1, ls="--")
        ax.axhline(0.5 if human else 100 / 3, color=INK_2, lw=0.8, ls=":")
        ax.annotate(f"{ref[bench]:.3f}" if human else f"{ref[bench]:.1f}", (0.3 if human else -0.36, ref[bench]),
                    xytext=(0, 2), textcoords="offset points", fontsize=6.5, color=INK_2, va="bottom")
        for j, (m, (name, color)) in enumerate(MODELS.items()):
            t = d[(d["bench"] == bench) & (d["model"] == m)].set_index("order").loc[list(ORDERS)]
            x = xs + (-0.06 if j == 0 else 0.06)
            ax.plot(x, t["rprec"], "-", color=color, lw=1.5, label=name)
            ax.errorbar(x, t["rprec"], yerr=[t["rprec"] - t["lo"], t["hi"] - t["rprec"]],
                        fmt="o", color=color, ms=5, mec="white", mew=1, elinewidth=0.9, capsize=0)
            for xx, v in zip(x, t["rprec"]):
                off = (-7, 0) if j == 0 else (6, 0) if human else (6, 4)
                ax.annotate(fmt.format(v), (xx, v), xytext=off, textcoords="offset points",
                            ha="right" if j == 0 else "left", va="bottom" if off[1] else "center",
                            fontsize=6.5, color=INK)
        labels = ["Best first", "Shuffled", "Best last"] if human else list(ORDERS.values())
        ax.set_xticks(xs, labels, fontsize=7)
        ax.set_xlim(-0.4, 2.45)
        ax.set_title(title, fontsize=8)
        ax.grid(axis="x", visible=False)
        ax.tick_params(axis="y", labelsize=7)
    for ax in axes[:2]:
        ax.set_ylim(10, 100)
    axes[1].set_yticklabels([])
    axes[0].set_ylabel("R-precision % (higher is better)", fontsize=7.5)
    axes[2].set_ylim(0.8, 0.15)  # inverted: better is up, as in the citation panels
    axes[2].set_ylabel("$\\tau$ loss (lower is better)", fontsize=7.5)
    handles = [plt.Line2D([], [], color=c, lw=1.5, marker="o", ms=4, label=n) for n, c in MODELS.values()]
    handles += [plt.Line2D([], [], color=INK_2, lw=1, ls="--", label="Qwen3-Embedding-8B (order-independent)"),
                plt.Line2D([], [], color=INK_2, lw=0.8, ls=":", label="random / constant ranking")]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=7, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(w_pad=1.2, rect=(0, 0.08, 1, 1))
    save(fig, "position_bias_3b_8b")
    print(d.round(1).to_string(index=False))


if __name__ == "__main__":
    fig_position_bias_models()
    fig_label_agreement()
