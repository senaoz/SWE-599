# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Academic publication recommendation system that matches global papers (from followed institutions) to local BOUN researcher expertise using multiple embedding methods. Notebook-based research project — all primary logic lives in Jupyter notebooks.

## Environment Setup

```bash
pip install -r requirements.txt
```

Requires a `.env` file with:
```
GEMINI_API_KEY=<your_key>
```

## Notebook Execution Order

Run in sequence (each depends on outputs from the previous):

1. `fetch_and_preprocessing.ipynb` — fetches from OpenAlex API, reconstructs abstracts, extracts keywords → `data/cleaned/{boun,priority_followed}.csv`
2. `similarity_evaluation.ipynb` — main evaluation: runs BM25, MiniLM, SPECTER2, Qwen, Gemini across tasks, generates visualizations
3. `week3_cited_paper_ranking.ipynb` — cited paper ranking evaluation with structured positives/negatives

`unused/build_eval_dataset.ipynb` builds the 100-pair benchmark (`eval_dataset/benchmark_pairs_with_related_works.json`) if it needs to be regenerated.

## Shared Python Modules (`src/`)

All reusable logic has been extracted from notebooks into:

- **`src/text_utils.py`** — `safe_parse`, `extract_concept_names`, `build_text(row, fields=('abstract','title','concepts'))`
- **`src/similarity.py`** — `bm25_similarity`, `tfidf_similarity`, `sentence_embedding_similarity`, `gemini_score_pair`; also exports `DEVICE`, `MODEL_MAP`, `MAX_TEXT_CHARS`, `BATCH_SIZES` constants
- **`src/metrics.py`** — two paradigms:
  - *ID-based* (large corpus, `similarity_evaluation.ipynb`): `ndcg_at_k`, `average_precision_at_k`, `reciprocal_rank_fusion`
  - *Index-based* (small candidate set, `week3_cited_paper_ranking.ipynb`): `hit_rate_at_n`, `reciprocal_rank`, `ndcg_at_n`

When adding new similarity methods or metrics, add them to `src/` first and import in notebooks.

## Caching Strategy

**Always check caches before recomputing** — some methods are expensive:

- Embedding `.npy` files → `data/embeddings_cache/` (default) or `data/embeddings_cache/week3/` (week3 notebook)
- Parsed DataFrames → `data/cleaned/`
- Evaluation results → `data/results_cache/`

`sentence_embedding_similarity` caches both corpus and query embeddings keyed by `(model_name, n_texts, md5_of_first_5_texts)`. Pass `cache_dir=EMBED_CACHE` when using a non-default path (as week3 does).

## Paper Representation

Each paper uses: `title`, `abstract` (reconstructed from OpenAlex inverted index), `concepts` (OpenAlex concept objects with `display_name`). The `build_text(row, fields=...)` function in `src/text_utils.py` combines these for similarity input. Field ablation studies test all combinations.

## Key Data Files

- `data/cleaned/boun.csv` — 4,608 BOUN papers
- `data/cleaned/priority_followed.csv` — 9,946 external papers
- `eval_dataset/benchmark_pairs_with_related_works.json` — 100 query-positive benchmark pairs

## API Notes

- **OpenAlex**: accessed via `pyalex` wrapper or direct `requests` calls; rate limits apply
- **Gemini**: `google-generativeai` package; configure with `genai.configure(api_key=...)` before calling `gemini_score_pair`; results cached to avoid repeated API calls
