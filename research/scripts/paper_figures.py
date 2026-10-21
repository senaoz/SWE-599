"""Figures for paper/main.tex that combine several notebooks' results.

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

from src.figures import FAMILY_COLOR, FIG_DIR, INK, INK_2, save, setup_style
from src.pipeline_v2 import load_runs
from src.stats_v2 import method_table, per_query

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
}
# label placement, chosen by eye: the three embeddings sit within a few points of each
# other, so their labels go to the empty upper left with leader lines
LEADER = {"qwen": (72, 0.183), "specter2": (72, 0.203), "minilm": (72, 0.223)}
OFFSETS = {"tfidf": (6, 4, "left"), "bm25": (-6, -8, "right"),
           "llama-pointwise": (6, -6, "left"), "llama": (6, 9, "left")}


def citation_scores() -> pd.DataFrame:
    """R-precision mean and CI per method, computed exactly as in v2/05_stats."""
    C = json.loads((V2 / "config.json").read_text())
    tag = f"{C['fields']}_{C['max_chars']}_{C['query_max_chars']}"
    df = load_runs("random", tag, split="test")
    df = df[~df["method"].str.contains("llama8b")]  # 05_stats predates the 8B runs
    table = method_table(per_query(df)).set_index("method")
    return table


def human_scores() -> pd.DataFrame:
    res = pd.concat([pd.read_csv(GS / "14_results.csv"), pd.read_csv(GS / "17_results.csv")])
    return res.drop_duplicates("method").set_index("method")


def main() -> None:
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
    ax.text(34.5, 0.415, "random ranking", fontsize=6.5, color=INK_2, va="center")
    ax.set_xlim(32, 92)
    ax.set_ylim(0.52, 0.17)  # inverted: better is up
    ax.set_xlabel("Citation labels: R-precision % (higher is better)", fontsize=8)
    ax.set_ylabel("Human labels: $\\tau$ loss (lower is better)", fontsize=8)
    ax.tick_params(labelsize=7)
    handles = [plt.Line2D([], [], marker="o", ls="", color=FAMILY_COLOR[f], label=f)
               for f in ("Lexical", "Embedding", "LLM")]
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(0.02, 0.5), fontsize=7, handletextpad=0.2)
    fig.tight_layout()
    save(fig, "fig3_label_agreement")
    print(d[["method", "rprec", "rprec_lo", "rprec_hi", "loss", "loss_lo", "loss_hi"]].round(3).to_string(index=False))
    print(f"Kendall tau between the two orderings (n={len(d)}): {tau:.3f}")


if __name__ == "__main__":
    main()
