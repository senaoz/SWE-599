# Research

Citation-based paper recommendation benchmark. Work proceeds in three stages: the original benchmark (v1), an audit of it, and a rebuilt, leak-free benchmark (v2).

```
research/
├── src/          shared library (also imported by backend/, so keep this path)
├── v1/           frozen v1 benchmark (git tag v1-results)
├── audit/        audit of v1: AUDIT.md + verify_v1.py
├── v2/           leak-free benchmark: run.py, eval_sets/, runs/
├── scripts/      utilities (remove_local_models.sh)
├── archive/      superseded or incomplete experiments
└── data/         local caches, gitignored
```

## Stage 1 — v1 (frozen)

The numbered notebooks are kept for reference. Results in `v1/results/` are byte-identical to tag `v1-results` (originally `eval_dataset/week3/`). The audit found the v1 evaluation invalid; see `audit/AUDIT.md` before citing any v1 number.

| Step | File | What it did |
|---|---|---|
| 01 | `v1/01_fetch_and_preprocessing.ipynb` | Fetch the OpenAlex corpora and preprocess them |
| 02 | `v1/02_similarity_evaluation.ipynb` | Early pairwise benchmark (`v1/pairs_benchmark/`) |
| 03 | `v1/03_cited_paper_ranking.ipynb` | Cited-paper ranking benchmark (`_out` = executed copy with outputs) |
| 04 | `v1/04_pipeline_demo.ipynb` | Two-stage pipeline demo |
| — | `v1/stats/significance.py` | Bootstrap CIs and Holm-corrected Wilcoxon tests → `v1/stats/results.md` |

The notebooks used paths relative to `research/` and depend on caches that no longer exist (see the audit), so they are not expected to re-run.

## Stage 2 — Audit

```bash
python research/audit/verify_v1.py
```

This reproduces every number in `audit/AUDIT.md` from `v1/results/`.

## Stage 3 — v2

All models run locally. The sentence-transformers models (MiniLM, SPECTER2, bge-reranker) run in-process. The GGUF models (Llama 3.2 3B, Qwen3-Embedding-8B, EmbeddingGemma) are served over an OpenAI-compatible API by [llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server` in router mode on `127.0.0.1:1337`. Use build b11146: it is the build Jan bundled for the earlier runs, and its outputs are bit-identical to Jan's. Each model is a preset section named after its model id (paths must be absolute):

```ini
[*]
ctx-size = 8192

[bartowski/Llama-3_2-3B-Instruct-Q4_K_M]
model = /path/to/gguf/bartowski/Llama-3_2-3B-Instruct-Q4_K_M/model.gguf
ctx-size = 16384

[Qwen/Qwen3-Embedding-8B-Q4_K_M]
model = /path/to/gguf/Qwen/Qwen3-Embedding-8B-Q4_K_M/model.gguf
embeddings = true
pooling = last
ctx-size = 0
batch-size = 2048
ubatch-size = 2048

[unsloth/embeddinggemma-300M-BF16]
model = /path/to/gguf/unsloth/embeddinggemma-300M-BF16/model.gguf
embeddings = true
pooling = mean
ctx-size = 0
batch-size = 2048
ubatch-size = 2048
```

```bash
llama-server --models-preset llama-server.ini --models-max 2 --host 127.0.0.1 --port 1337
```

`JAN_URL`, `JAN_API_KEY` and the model ids can be overridden with environment variables; see `src/jan.py`. The `JAN_` names are kept from when Jan served the models.

Setup, from `research/`:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name swe599-research
```

Run the numbered notebooks in order. Each one ends with a **Findings** cell and saves its paper figures, as PDF and SVG, to `v2/figures/`. Long notebooks can run in the background with papermill, which saves the notebook after every cell, so outputs appear while it runs:

```bash
.venv/bin/papermill v2/04_test_runs.ipynb v2/04_test_runs.ipynb --cwd v2 --log-output
```

| Step | Notebook | What it does | Needs llama-server |
|---|---|---|---|
| 01 | `v2/01_fetch_openalex.ipynb` | Fetch queries and references by OpenAlex id; normalize | no |
| 02 | `v2/02_build_eval_sets.ipynb` | Build `random` and `concept` benchmarks, dev/test split; sanity checks for every audit finding | no |
| 03 | `v2/03_dev_tuning.ipynb` | Choose text config and stage-1 k on dev → `v2/config.json` | yes |
| 04 | `v2/04_test_runs.ipynb` | All methods on test; LLM methods with 5 shuffle seeds; position-bias conditions | yes |
| 05 | `v2/05_stats.ipynb` | Bootstrap CIs, Holm-corrected Wilcoxon, seed spread → `v2/stats/` | no |
| 06 | `v2/06_analysis.ipynb` | Position bias, stage-1 recall@k, contamination, LLM reliability | no |

Code lives in `src/`:
- `pipeline_v2.py`: the steps
- `eval_v2.py`: pools, splits, candidate order
- `rankers_v2.py`: methods
- `stats_v2.py`: statistics and analyses
- `figures.py`: paper figures

The two benchmarks differ only in their negatives. Both draw them from other queries' references published before the query paper, excluding the query's own references and shared authors.

| Bench | Negatives |
|---|---|
| `random` | Sampled uniformly from that pool |
| `concept` | Must share one of the query's top-5 OpenAlex concepts (harder) |

Per-query run files are JSONL and resumable. Each record holds:
- the candidate order shown to the model and the full ranking, as OpenAlex ids
- the LLM status and raw response
- the metrics: MRR, R-precision, nDCG@n, AP, recall@k

`text tag` is `<fields>_<candidate max chars>_<query max chars>`, where fields are `t`itle, `a`bstract and `c`oncepts.
