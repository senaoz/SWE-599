# v1 vs v2: before and after the audit

- **v1:** tag `v1-results`, 100 queries, results in `v1/stats/results.md`. The audit (`AUDIT.md`, F1–F9) found the v1 evaluation invalid, so v1 numbers are shown only to document the change.
- **v2:** branch `v2-audit`, 118 test queries, results in `v2/stats/results_<bench>.md`, notebooks `v2/01`–`06`.

**This is not a paired re-run.** v2 rebuilds the candidate pools for the same query papers. v1's pools cannot be regenerated: its caches are gone and its seeds came from Python's salted `hash()` (F8).

## Headline claims

| v1 claim | v2 result |
|---|---|
| Listwise Llama 3.2 3B is the best method (MRR 0.841 vs Qwen3 0.513) | Listwise Llama is the **worst** method: R-precision 43.9 / 42.0, about 40 points below Qwen3 (p ≈ 2e-19) and close to chance (33.3). |
| The LLM's advantage reflects relevance judgement | **Position bias.** The same model on the same test queries scores MRR 0.95 / 0.98 with v1's positives-first order and 0.33 / 0.27 with positives last, below chance. |
| Two-stage Qwen3 → Llama (MRR 0.589) falls short because stage 1 loses references | Stage 1 keeps about 90% of references in its top 10 and 98–99% in its top 20. Two-stage (k = 10) is 13.0 / 10.4 points **below Qwen3 alone**: the Llama reranking step is what hurts. |
| Embedding models are roughly equivalent and weak (MRR 0.47–0.54, R-precision 30–37%) | Embedding models are the **best** methods, at 76–87% R-precision. The v1 values were at chance because positives carried other papers' text (F6). |
| SPECTER2 is among the weakest models | SPECTER2 is within 1 point of MiniLM and about 3–4 points of Qwen3, after fixing its pooling (F9). |

## Method by method

v2 values are given as `random` / `concept`. R-precision is the primary metric; v2 MRR saturates near 1.0 for the embedding models on `random`. Chance level is MRR ≈ 0.56 and R-precision 33.3% in both versions.

| Method | v1 MRR | v1 R-prec % | v2 MRR | v2 R-prec % [95% CI] |
|---|---|---|---|---|
| Qwen3-Embedding-8B | 0.513 | 37.4 | 0.987 / 0.970 | **87.0** [84.2, 89.7] / **80.1** [77.0, 83.0] |
| EmbeddingGemma | 0.471 | 34.0 | 1.000 / 0.983 | 85.6 [82.7, 88.4] / 78.5 [75.4, 81.4] |
| Qwen3 + MiniLM | 0.526 | 37.2 | 0.986 / 0.957 | 85.6 [82.6, 88.5] / 78.2 [74.8, 81.3] |
| SPECTER2 | 0.465 | 30.2 | 0.976 / 0.947 | 83.5 [80.5, 86.4] / 76.6 [73.3, 79.9] |
| MiniLM | 0.536 | 35.9 | 0.985 / 0.957 | 83.3 [80.2, 86.3] / 75.7 [72.1, 79.2] |
| TF-IDF | 0.536 | 33.4 | 0.921 / 0.880 | 75.3 [72.3, 78.3] / 65.4 [61.8, 69.0] |
| BM25 | 0.410 | 23.1 | 0.904 / 0.856 | 68.6 [65.5, 71.5] / 63.4 [60.0, 66.7] |
| Two-stage Qwen3 → Llama | 0.589 | 37.0 | 0.879 / 0.855 | 74.0 [71.4, 76.6] / 69.7 [67.0, 72.3] |
| Llama + MiniLM | 0.522 | 34.5 | 0.966 / 0.935 | 69.0 [66.9, 71.1] / 63.7 [61.3, 66.2] |
| **Llama listwise (full list)** | **0.841** | **45.0** | 0.662 / 0.638 | **43.9** [41.9, 46.0] / **42.0** [40.2, 43.9] |
| Llama sliding window *(new)* | — | — | 0.797 / 0.777 | 55.6 [53.5, 57.8] / 52.2 [49.9, 54.5] |
| Llama pointwise *(new)* | — | — | 0.947 / 0.928 | 78.8 [75.6, 81.9] / 73.9 [70.5, 77.3] |
| bge-reranker-base *(new)* | — | — | 0.912 / 0.872 | 67.2 [63.3, 71.0] / 58.1 [54.4, 61.8] |

## What changed between v1 and v2

| Area | v1 | v2 | Audit |
|---|---|---|---|
| Candidate order | positives first | shuffled per query and seed; order stored | F1 |
| LLM prompt | example `[3, 1, 7, ...]` pointing at a positive | no example indices | F2 |
| LLM failure | original order (positives first) | random order; status logged per call | F3 |
| Candidate fields | negatives lacked concepts; positives' text came from other papers | one normalized record per OpenAlex id, asserted; identical fields | F4, F6 |
| nDCG | normalized by retrieved hits | normalized by ideal ranking | F7 |
| Seeds | salted `hash()` | sha256 | F8 |
| SPECTER2 / EmbeddingGemma | mean pooling / unverified | [CLS] pooling / full model with Dense layers | F9 |
| Negatives | random 2020+ corpus papers | other queries' references published before the query; `random` and `concept` benchmarks | — |
| Tuning | none; all reported on the evaluation set | text config and stage-1 k chosen on 50 dev queries; 118 test queries | — |
| Seeds for LLM methods | 1 | 5 shuffle seeds (sd of R-precision 0.8–2.0) | — |
| Models | Ollama + Gemini/Kimi (excluded) | local only: llama-server (GGUF) + sentence-transformers | — |

## Limitations carried into v2

- **Negatives.** `concept` negatives often share only a broad field label (e.g. "Medicine") with the query. They are harder than `random`, but not same-topic hard negatives.
- **Duplicate positives.** 17 of 1,247 positives are duplicate OpenAlex records of a paper already among the positives.
- **Contamination.** It could not be tested: only one test query was published after Llama 3.2's December 2023 cutoff.
- **Embedding prompts.** Qwen3-Embedding and EmbeddingGemma run without their recommended instruction prefixes, for parity with v1.
- **bge-reranker truncation.** bge-reranker-base truncates query-candidate pairs at 512 tokens.
