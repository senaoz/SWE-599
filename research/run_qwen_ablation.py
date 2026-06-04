"""
Run Qwen field ablation on the Week 3 cited-paper-ranking benchmark.
Evaluates 4 text field combinations using Qwen3 embeddings via Ollama.
Results are saved to data/results_cache/ablation_results.pkl and a figure
is written to eval_dataset/field_ablation.png.
"""
import os
import json
import pickle
import random
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src.similarity import ollama_embedding_similarity

OLLAMA_MODEL = "qwen3-embedding:latest"
EMBED_CACHE  = "data/embeddings_cache"
CACHE_DIR    = "data/results_cache"
os.makedirs(EMBED_CACHE, exist_ok=True)

N_QUERIES = 100
RANDOM_SEED = 42

# ── Load benchmark ────────────────────────────────────────────────────────────
with open("data/results_cache/week3/eval_sets.pkl", "rb") as f:
    eval_sets = pickle.load(f)

with open("eval_dataset/week3/main_papers.json", "r") as f:
    main_papers_raw = json.load(f)

# Index main_papers by OpenAlex ID
main_by_id = {p["id"]: p for p in main_papers_raw}

# Sample 100 queries
random.seed(RANDOM_SEED)
sampled = random.sample(eval_sets, N_QUERIES)

print(f"Benchmark: {N_QUERIES} queries (sampled from {len(eval_sets)})")

# ── Field combinations ────────────────────────────────────────────────────────
def safe_str(val):
    if val is None or (isinstance(val, float)):
        return ""
    return str(val).strip()

FIELD_COMBOS = [
    ("Title only",                   lambda p, ca: safe_str(p.get("title"))),
    ("Abstract only",                lambda p, ca: safe_str(p.get("abstract"))),
    ("Title + Abstract",             lambda p, ca: " ".join(filter(None, [safe_str(p.get("title")), safe_str(p.get("abstract"))]))),
    ("Title + Abstract + Concepts",  lambda p, ca: " ".join(filter(None, [safe_str(p.get("title")), safe_str(p.get("abstract")), " ".join(ca or [])]))),
]


def build_candidate_text(cand, field_fn):
    concepts_array = cand.get("concepts_array", [])
    return field_fn(cand, concepts_array)


def build_query_text(pi_id, pi_title, field_fn):
    mp = main_by_id.get(pi_id)
    if mp:
        return field_fn(mp, mp.get("concepts_array", []))
    # Fallback: title only (abstract not available for this query paper)
    return pi_title


# ── Metrics ───────────────────────────────────────────────────────────────────
def compute_metrics(ranked_indices, n_positives, total):
    """ranked_indices: list of candidate indices sorted by score desc.
       First n_positives items in the candidate list are the positives."""
    positive_set = set(range(n_positives))
    mrr = 0.0
    for rank, idx in enumerate(ranked_indices, 1):
        if idx in positive_set:
            mrr = 1.0 / rank
            break

    # Hit rate: fraction of positives recovered in top-n% (where n = n_positives)
    cutoff = n_positives
    hits = sum(1 for idx in ranked_indices[:cutoff] if idx in positive_set)
    hr = hits / n_positives if n_positives > 0 else 0.0

    # nDCG@cutoff
    dcg = sum(
        1.0 / np.log2(rank + 2)
        for rank, idx in enumerate(ranked_indices[:cutoff])
        if idx in positive_set
    )
    idcg = sum(1.0 / np.log2(rank + 2) for rank in range(min(n_positives, cutoff)))
    ndcg = dcg / idcg if idcg > 0 else 0.0

    return mrr, hr, ndcg


# ── Run ablation ──────────────────────────────────────────────────────────────
cache_path = os.path.join(CACHE_DIR, "ablation_results.pkl")
if os.path.exists(cache_path):
    with open(cache_path, "rb") as f:
        ablation_results = pickle.load(f)
    print(f"Loaded existing cache with keys: {list(ablation_results.keys())[:4]}...")
else:
    ablation_results = {}

results_qwen = {}

for label, field_fn in FIELD_COMBOS:
    key = (label, "qwen")
    if key in ablation_results:
        print(f"[SKIP] {label} — already cached")
        results_qwen[label] = ablation_results[key]
        continue

    print(f"\n{'='*60}")
    print(f"Field: {label}")
    print(f"{'='*60}")

    mrr_list, hr_list, ndcg_list = [], [], []

    for i, es in enumerate(sampled):
        pi_id    = es["pi_id"]
        pi_title = es["pi_title"]
        n_pos    = es["n_positives"]
        positives = es["positives"]
        negatives = es["negatives"]

        query_text = build_query_text(pi_id, pi_title, field_fn)
        if not query_text.strip():
            query_text = pi_title

        # Build candidate texts (positives first, then negatives)
        candidate_texts = (
            [build_candidate_text(c, field_fn) or c.get("title", "") for c in positives] +
            [build_candidate_text(c, field_fn) or c.get("title", "") for c in negatives]
        )

        sim = ollama_embedding_similarity(
            [query_text], candidate_texts,
            model_name=OLLAMA_MODEL,
            cache_dir=EMBED_CACHE,
        )[0]

        ranked = list(np.argsort(sim)[::-1])
        mrr, hr, ndcg = compute_metrics(ranked, n_pos, len(candidate_texts))
        mrr_list.append(mrr)
        hr_list.append(hr)
        ndcg_list.append(ndcg)

        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{N_QUERIES} — MRR={np.mean(mrr_list):.3f}  HR={np.mean(hr_list):.3f}  nDCG={np.mean(ndcg_list):.3f}")

    result = {
        "mrr":      float(np.mean(mrr_list)),
        "mrr_std":  float(np.std(mrr_list)),
        "hr":       float(np.mean(hr_list)),
        "hr_std":   float(np.std(hr_list)),
        "ndcg":     float(np.mean(ndcg_list)),
        "ndcg_std": float(np.std(ndcg_list)),
        "mrr_list":  mrr_list,
        "hr_list":   hr_list,
        "ndcg_list": ndcg_list,
    }
    results_qwen[label] = result
    ablation_results[key] = result
    print(f"  → MRR={result['mrr']:.3f}  HR={result['hr']:.3f}  nDCG={result['ndcg']:.3f}")

# Save updated cache
with open(cache_path, "wb") as f:
    pickle.dump(ablation_results, f)
print(f"\nSaved cache to {cache_path}")

# ── Print summary table ───────────────────────────────────────────────────────
print(f"\n{'Fields':<35} {'MRR':>7} {'HR@n%':>7} {'nDCG@n':>8}")
print("─" * 60)
for label, _ in FIELD_COMBOS:
    r = results_qwen[label]
    print(f"{label:<35} {r['mrr']:>7.3f} {r['hr']:>7.3f} {r['ndcg']:>8.3f}")

# ── Figure ────────────────────────────────────────────────────────────────────
labels = [label for label, _ in FIELD_COMBOS]
short_labels = ["Title\nonly", "Abstract\nonly", "Title +\nAbstract", "Title + Abs.\n+ Concepts"]
mrr_vals  = [results_qwen[l]["mrr"]  for l, _ in FIELD_COMBOS]
hr_vals   = [results_qwen[l]["hr"]   for l, _ in FIELD_COMBOS]
ndcg_vals = [results_qwen[l]["ndcg"] for l, _ in FIELD_COMBOS]

x = np.arange(len(labels))
width = 0.28

fig, ax = plt.subplots(figsize=(10, 5))
bars1 = ax.bar(x - width, mrr_vals,  width, label="MRR",    color="#8e44ad", alpha=0.85)
bars2 = ax.bar(x,          hr_vals,   width, label="HR@n%",  color="#2980b9", alpha=0.85)
bars3 = ax.bar(x + width,  ndcg_vals, width, label="nDCG@n", color="#27ae60", alpha=0.85)

for bars, vals in [(bars1, mrr_vals), (bars2, hr_vals), (bars3, ndcg_vals)]:
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{val:.3f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(short_labels, fontsize=10)
ax.set_ylabel("Score")
ax.set_title("Field Ablation — Qwen3 Embeddings (100 queries)")
ax.legend()
ax.grid(True, alpha=0.3, axis="y")
ax.set_ylim(0, max(max(mrr_vals), max(hr_vals), max(ndcg_vals)) * 1.25)

plt.tight_layout()
fig_path = "eval_dataset/field_ablation.png"
plt.savefig(fig_path, dpi=150, bbox_inches="tight")
print(f"Saved figure to {fig_path}")
