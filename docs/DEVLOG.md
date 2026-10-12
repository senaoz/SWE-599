# Development log (SWE 599, Spring 2026)

Week-by-week working notes kept during the project. The research summary and final results are in the [main README](../README.md); where numbers here differ, the README and final report are authoritative.

## Week 1: Data Fetching & Benchmark Dataset

The immediate goal is to establish a benchmark dataset to evaluate different vectorization methods.

**Completed tasks:**

- **Data Collection:** Fetched 4,608 BOUN papers and 9,946 followed institution papers (post-2020) via the OpenAlex API.
- **Preprocessing:** Reconstructed abstracts from inverted index format; applied HTML cleaning, URL removal, stopword filtering, and keyword extraction. Cleaned data saved under `research/data/cleaned/`.
- **Benchmark Dataset:** Built 100 query-positive pairs using a 3-tier matching strategy — citation network (gold), topic/keyword overlap (silver), and concept fallback (bronze) (`research/eval_dataset/benchmark_pairs_with_related_works.json`).
- **Co-authoring Analysis:** Analyzed BOUN's top collaborating institutions (CNRS, Istanbul University, CERN, etc.) and research domains (particle physics, earthquake studies, etc.).

---

![swe599-1](https://github.com/user-attachments/assets/2920ef9f-2d3a-4889-95cb-e7c49ca2501e)
![swe599-2](https://github.com/user-attachments/assets/23c690d6-0736-4f35-a2e8-f82cf954e82e)

---

## Week 2-3: Dataset for Performance Evaluation & Embedding Comparison

Since the project relies on finding "similar" content, selecting the most accurate embedding model is critical. This week focuses on building the similarity pipeline and evaluating it across different methods and scopes.

> **Implementation note (applies to all tasks below):**
> The similarity scoring function must accept a `fields` parameter to toggle which data is used — `abstract`, `title`, and/or `concepts`. Default: all three combined.

---

### Task 1 — Cross-Corpus Similarity (External → BOUN)

**1a. External-to-BOUN Retrieval**

- Sample 50 papers from a followed institution (e.g. MIT).
- For each paper, compute similarity scores against all BOUN papers.
- Return the top-3 most similar BOUN papers per query.

**1b. BOUN-to-External Retrieval**

- Sample 50 papers from the BOUN corpus.
- For each paper, compute similarity scores against all followed-institution papers.
- Return the top-3 most similar external papers per query.

---

### Task 2 — Embedding Method Comparison

Run Task 1 using the following similarity methods and compare results:

| Method | Description |
|---|---|
| **TF-IDF + Cosine** | Sparse vector baseline |
| **Sentence Embeddings** | e.g. `all-MiniLM`, `SPECTER2`, `Google Embdedding`, `Quwen`, `BM25` |
| **Gemini API** | Prompt Gemini to score semantic similarity between two papers directly |

Produce a comparison table: for each method, report top-3 retrieved papers per query along with similarity scores. Evaluate against the benchmark pairs from Week 1 where applicable.

---

### Task 3 — Intra-Paper Similarity

These tasks validate that the similarity pipeline ranks known-relevant papers highly, serving as a qualitative sanity check.

**3a. Same-Author Paper Ranking**

- Given a target paper, retrieve all other papers by the same author(s) from the BOUN corpus.
- Rank them by similarity score to the target paper.
- Expected: thematically related works by the same author should rank near the top.

**3b. Cited Paper Ranking**

- Given a target paper, retrieve its reference list (papers it cites) from the dataset.
- Rank the cited papers by similarity score to the target paper.
- Expected: directly cited works should score higher than unrelated papers, validating the embedding quality.

## Week 4-5: Detailed Cited Paper Ranking Dataset for Method Evaluation

![IMG_2572](https://github.com/user-attachments/assets/5260e0c9-7734-40c7-b189-322c502f0a70)

Week 3 constructs a cited paper ranking dataset using papers from `research/data/cleaned/priority_followed.csv` (followed institutions) to test how embedding methods prioritize true references over random distractors from the followed corpus.

This extends Week 2's Task 3b with structured positives (citations) and hard negatives, enabling quantitative ranking metrics like precision@k. Reference lists are accessed via OpenAlex IDs or API fetches from the dataset metadata.

### Step 1: Select Main Papers (P_i)

Randomly sample 100 papers (P_i) from `priority_followed.csv` where each has 6-14 references (refCount ∈ ).

- Filter by `referenced_works_count` or equivalent field.
- Ensure references are resolvable in the corpus or fetchable via OpenAlex.

Output: `research/eval_dataset/week3/main_papers.json` with 100 P_i metadata.

### Step 2: Build Per-P_i Evaluation Set

For each P_i (refCount = n):

- Positives: n actual references (prioritize those in followed corpus; fetch abstracts/titles via OpenAlex otherwise).
- Negatives: 2n random papers from `priority_followed.csv`, excluding P_i's references and same-author works for hard negatives.

Result: Per P_i set of 3n candidates (n positives + 2n negatives); P_i as query.

### Step 3: Compute Embeddings and Rankings

Embed P_i (title/abstract/concepts) and 3n candidates using Week 2 methods: TF-IDF + Cosine, Sentence Transformers, Gemini API, Google Embedding Model.

- Rank all 3n candidates by similarity score to P_i.
- In top-n results: Count how many (a) are true references out of n slots; compute hit rate = (a / n) × 100%.

Save: `research/eval_dataset/week3/rankings_{method}.json` with full ranks, scores, and per-query hit rates.

### Step 4: Evaluation Metrics and Comparison

Aggregate across 100 queries; report per-method: Mean, Std Dev, Median.

- Hit Rate %: Average percentage of top-n filled by true references.

#### Gemini Ranking Approach

Instead of scoring each candidate individually (one API call per paper), Gemini ranks all candidates in a **single prompt**. For each query, the prompt contains:

- **Main Paper** (title + abstract, up to 800 chars)
- **Candidate Papers 1–N** (18–42 papers, up to 600 chars each)

Gemini returns a JSON array of candidate numbers ordered by relevance, e.g. `[7, 2, 15, ...]`. Scores are derived from rank position: rank-1 → `1.0`, rank-N → `~0.0`.

- Gemini compares candidates *relative to each other*, not in isolation
- Fits comfortably within Gemini 2.5 Flash's 1M-token context window

**Implementation:** `gemini_rank_candidates(query_text, candidates)` in `research/src/similarity.py`.


### Week 6–12 — Full-Stack Application

Built a production-ready recommendation system on top of the Week 1–3 research pipeline. See [README_APP.md](../README_APP.md) for setup and run instructions.

### Features

- **Auth** — JWT register/login; all routes protected
- **Institution follow** — search OpenAlex, follow/unfollow institutions; papers fetched automatically
- **Paper recommendations** — paginated dashboard; top-5 matching BOUN researchers per paper with modal detail view
- **Researcher profiles** — searchable list of 2671 BOUN researchers with publication history and detail pages
- **Feedback** — thumbs up/down on paper–researcher matches to collect relevance signal
- **Admin panel** — switch active embedding model, manually trigger matching job, view system stats
- **Dark mode** — full UI theming with system preference detection

### 2-Stage RAG Matching Pipeline

Every 6 hours (or on manual trigger via Admin):

1. **Fetch** — new papers from followed institutions via OpenAlex API
2. **Stage 1 — Retrieve** — embed papers with nomic-embed-text; cosine similarity against ~7800 individual BOUN paper embeddings; top-20 researchers by max score
3. **Stage 2 — Rerank** — top-10 researchers sent to Llama 3.2 with context (new paper + top-3 matching BOUN papers); LLM returns a relevance score used as final score
4. **Store** — `PaperResearcherMatch` rows persisted (only if score ≥ 0.3)

### Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + SQLAlchemy (async) + PostgreSQL 16 |
| Embeddings | Ollama (nomic-embed-text, llama3.2) / SentenceTransformer |
| Frontend | React 19 + TypeScript + Vite + Tailwind CSS |
| Infra | Docker Compose |

---

## v2 audit and rebuild (October 2026)

Branch `v2-audit`, PR senaoz/SWE-599#1. v1 results are frozen under tag `v1-results` (614cfb2). The aim is to check whether the v1 headline (Llama listwise reranker MRR 0.84 vs Qwen3 0.51) holds before using it in PhD applications. Each entry gives what was done, why, and the evidence, with the commit in brackets.

### 2026-10-09 — Audit of v1 (`research/audit/AUDIT.md`) [91d5161]

- **What.** Reproduced the external review's findings from the saved rankings, and found three more. Numbers are in `AUDIT.md` and reproduced by `audit/verify_v1.py`.
- **Review findings, confirmed.**
  - **F1:** positives were always shown first.
  - **F2:** the prompt example `[3, 1, 7, ...]` pointed at a positive. Llama put candidate 3 first in 33/100 queries; other methods did this in 2–8/100.
  - **F3:** a failed call fell back to the original order (3 Llama queries).
  - **F4:** negatives had no concept tags, while the LLM input was title + concepts.
  - **F5:** on the 25 queries where stage 1 removes nothing, two-stage (0.526) scored below Qwen3 alone (0.580). So "stage-1 recall loss" cannot explain the drop.
- **New findings.**
  - **F6:** positives were given *other papers'* text. A DataFrame index label was used as a row position after a sort and filter. This explains why every non-LLM method was at or below chance (chance MRR 0.556; BM25 R-precision 23.1%, CI below chance).
  - **F7:** nDCG was normalized by the method's own hits.
  - **F8:** negatives were sampled with Python's salted `hash()`, so v1 pools cannot be rebuilt.
- **Consequence.** The v1 numbers should not be cited. The v1 caches (`eval_sets.pkl`, `rankings.pkl`, corpus) no longer exist, so v2 rebuilds the pools for the same queries. This is not a paired re-run.

### 2026-10-11 — Local models only, served by Jan [8fa5c66, e90f8ad, e2a14c2]

- **Decision.** Drop cloud models (Gemini, Kimi, Ollama Cloud) and Ollama. GGUF models run in Jan's local OpenAI-compatible API (`src/jan.py`). MiniLM, SPECTER2 and bge-reranker stay in-process (sentence-transformers).
- **Quantizations.** These match v1's Ollama setup:
  - Llama 3.2 3B Instruct Q4_K_M
  - Qwen3-Embedding-8B Q4_K_M
  - EmbeddingGemma BF16
- **Pooling problem.** Jan registered Qwen3-Embedding with mean pooling. The llama.cpp log showed `model default pooling_type is [3], but [1] was specified`. It was set to last-token pooling (the model's default) and verified (no warning; cosine changed 0.557 → 0.463). Without this, Qwen3 results would have been silently wrong.
- **Context.** Llama context was set to 16,384 tokens; the largest listwise prompt is about 5.2k tokens.
- **Cleanup.** `research/scripts/remove_local_models.sh` removes all downloaded models later.

### 2026-10-11 — v2 data and benchmarks [a149cac, 591484e, 10ae589]

- **Fetch.** The 174 v1 query papers and all 1,729 listed references were fetched by OpenAlex id. 155 references are deleted from OpenAlex (404). Every record is normalized by one function, so all candidates have identical fields and an asserted id (fixes F4, F6).
- **Eligibility.** Every candidate needs a title and an abstract; v1 required this only for negatives. 168 queries remain: 50 dev and 118 test, split with a sha256 seed (fixes F8).
- **Negative pool.** Other queries' references, published before the query and sharing no author with it. **Chosen over a random corpus sample** so that positives and negatives share the same "cited work" distribution. The v1 corpus was the first 10,000 of 505,882 papers because of OpenAlex's paging cap, i.e. not a random sample.
- **Two benchmarks** (user decision: report both).
  - **Why.** With random negatives, MRR saturated on dev (TF-IDF 1.000, MiniLM 1.000).
  - **`random`:** negatives sampled uniformly from the pool. Only 30% share a top-5 OpenAlex concept with the query, against 74% of positives.
  - **`concept`:** negatives must share one; 98% do, more than the positives.
  - **Primary metric.** R-precision, because MRR saturates on `random`.
- **Order and failures.** Candidates are shuffled per query and seed, and the shown order is stored (fixes F1). The prompt has no example indices (fixes F2). A failed call falls back to a random order, and every call's status is logged (fixes F3).
- **Metrics.** nDCG now uses the ideal ranking (fixes F7).

### 2026-10-11 — Repository layout and notebooks [92e7fb3, e04eeff]

- **Layout.** `research/` was reorganized into `v1/` (frozen, numbered notebooks), `audit/`, `v2/` and `archive/`. `v1/results/` is byte-identical to the old `eval_dataset/week3/`, and the v1 statistics reproduce exactly.
- **Notebooks.** v2 runs as numbered notebooks 01–06 (user request: v1 style, with outputs and figures for the paper). They execute with papermill, which saves after every cell. Paper figures go to `v2/figures/` as PDF and SVG, using a palette validated for colour-vision deficiency.

### 2026-10-12 — Dev tuning (`v2/03_dev_tuning.ipynb`) [31dad82]

- **Text config.** One shared candidate text for all methods, chosen by mean rank across methods and both benchmarks: **title + abstract + concepts, 600 chars** (mean rank 1.75, vs 1.88 for title + abstract).
- **Listwise Llama is the weakest method.** R-precision is 44–55% against 82–89% for Qwen3 and about 33% for a random ranking, with 26–48% partial outputs. Inspection of the raw outputs shows the model largely **copies the input order**: the first-shown candidate is ranked first in 58% of dev queries. This is a likely mechanism for v1's 0.84, since there positives were always first. The position-bias experiment in notebook 06 will test it directly.
- **Two-stage gets worse as Llama sees more candidates.** On `random`, k = 10, 20, 30 give 78.4, 54.2 and 43.6, all below Qwen3 alone (88.7). k = 10 is used on test as the least harmful setting.
- **bge-reranker degrades with longer text.** Its 512-token limit truncates the long query-candidate pairs.

### 2026-10-12 — Sliding-window listwise variant [a79313e]

- **Why.** So that Llama is not judged only by its long-list failure mode (user decision).
- **Method.** RankGPT-style: windows of 10 moving 5 at a time, from the bottom of the shuffled list to the top. The model never sees more than 10 candidates.
- **Dev result.** Output becomes reliable: 199 of 200 window calls parse fully, against 26–48% partial answers for the full list. R-precision rises 46.9 → 54.0 on `random` and 43.6 → 53.6 on `concept`. It is still far below Qwen3 (88.7 / 81.3) and below bge-reranker (70.2 / 55.7). The first-shown candidate still ends up first in 40–52% of queries, so order copying remains.
- **Decision.** Include it in the test runs (5 seeds) as the strongest listwise setting, so the LLM comparison is fair. Cost on dev is about 6.5 s per query (4 calls on average).

### 2026-10-12 — Scope of the test runs

- **Methods on test (12).**
  - Lexical: BM25, TF-IDF.
  - Embeddings: MiniLM, SPECTER2, Qwen3-Embedding-8B, EmbeddingGemma.
  - Fusions: Qwen3 + MiniLM, Llama + MiniLM.
  - Cross-encoder: bge-reranker-base.
  - LLM: listwise Llama (full list), sliding-window Llama, pointwise Llama, two-stage Qwen3 → Llama (k = 10).
- **Seeds.** Order-sensitive LLM methods run with 5 shuffle seeds; order-independent methods with 1.
- **Known limitation.** Qwen3-Embedding and EmbeddingGemma run without their recommended instruction prefixes, for parity with v1.
- **Position-bias experiment kept in full** (user decision). Listwise Llama on both benchmarks, with candidates in v1's positives-first order and reversed, against the shuffled runs. These conditions are not reported as methods. They are the controlled test of whether v1's MRR 0.84 came from order copying instead of content, which so far rests on indirect dev evidence (the first-shown candidate is ranked first in 58% of queries).

### 2026-10-12 — Model server and encoder fixes [9ec3b00, 7d98672]

- **Model server.** GGUF models moved from Jan to a standalone `llama-server` (launchd, 127.0.0.1:1337) with the same files and settings: Qwen3 last-token pooling, Llama context 16,384 [9ec3b00].
- **Pooling check, prompted by the question of what each model's pooling should be.** Two encoders were wrong. Both were fixed before the test runs, and both affected v1 too.
  - **SPECTER2** was loaded through sentence-transformers' default, which silently adds **mean** pooling to plain transformers checkpoints. The model is trained with its **[CLS]** token. It is now built explicitly with CLS pooling, and its output matches a manual `last_hidden_state[:, 0]` to within 2e-6. Added to the audit as **F9**.
  - **EmbeddingGemma's GGUF** (`unsloth/embeddinggemma-300M-BF16`) has no `dense_*` tensors, so it was missing the two Dense projection layers (768 → 3072 → 768) after mean pooling. Its vectors correlated about 0.00 with the reference model's. It now runs in-process as `unsloth/embeddinggemma-300m` (sentence-transformers, Dense layers included; an ungated mirror of Google's weights, 1.3 GB).
- **Cache safety.** Embedding cache files now carry an encoder version, so stale vectors cannot be reused after a change like this.
- **Effect on dev** (title + abstract + concepts). Both models moved close to Qwen3 (88.7 / 81.3):
  - SPECTER2: 82.6 → 87.2 on `random`, 73.1 → 78.1 on `concept`.
  - EmbeddingGemma: 85.7 → 88.4 on `random`, 79.2 → 80.3 on `concept`.
- **Stray run file.** A dev seed-1 Llama file of unknown origin (16 queries, possibly a manual notebook run) had entered the tuning summary and shifted the config choice. It was moved to `data/v2/stray/`. Dev tuning now averages over seeds before ranking. With that, the choice is unchanged: title + abstract + concepts (mean rank 1.75), k = 10.

### 2026-10-12 — Test runs started [a7b3519]

- **Concurrency test.** llama-server has 4 slots, so concurrent requests were tested on 12 dev queries with full-list Llama.
  - **Outputs:** identical to the sequential run (12/12 raw responses and rankings).
  - **Speed:** no gain (44 s vs 41 s). The LLM work is dominated by prompt processing (1–5k tokens per call, about 1,000 tokens/s on the M1 Max), which already saturates the GPU.
  - Runs stay sequential. The option is kept in code (`RunConfig.workers`).
- **Run order.** Test runs are ordered so that a complete result exists early:
  1. All methods on both benchmarks with **3 core seeds** for the order-sensitive LLM methods, plus pointwise and the position-bias conditions (about 5.5 h).
  2. Then seeds 3 and 4 (about 3 h).
- **Started** 2026-10-12 08:15, under `caffeinate`. Log: `research/data/v2/logs/04_test_runs.log`.

### 2026-10-12 — Note on what `concept` negatives are

Inspecting test examples shows that the `concept` match often rests on a very broad OpenAlex concept. For example, a query on reproducibility of ML in health care gets negatives about neonatal screening and an antibody-drug conjugate, which share only "Medicine". `concept` negatives therefore come from the same broad field, not necessarily the same topic, and some `random` negatives happen to be closer.

This is a limitation for the paper. `concept` is a harder setting, not a true hard-negative benchmark. Same-subtopic hard negatives belong to the full-corpus retrieval experiment (Phase 4).

**Example** (test query `W2997681568`, 2020-01-06; same in both benchmarks except the negatives). The query is *Challenges to the Reproducibility of Machine Learning Models in Health Care*. Its top-5 concepts are Medicine, Reproducibility, Machine learning, Health care, Artificial intelligence.

| Role | Paper (year) | Shared top-5 concepts with query |
|---|---|---|
| Positive | Estimating the reproducibility of psychological science (2015) | Reproducibility |
| Positive | Why Most Published Research Findings Are False (2005), `W2144981148` | Medicine |
| Positive | Why Most Published Research Findings Are False (2005), `W2331384579` | — |
| Positive | Deep Learning—A Technology With the Potential to Transform Health Care (2018) | Medicine, Deep learning → AI |
| `random` negative | Real-time human interaction with supervised learning algorithms for music composition and performance (2011) | Machine learning, AI |
| `random` negative | Strengthening Health Systems While Responding to a Health Crisis… Ebola… Sierra Leone (2016) | — |
| `random` negative | Within host RNA virus persistence: mechanisms and consequences (2017) | — |
| `random` negative | Dissecting racial bias in an algorithm used to manage the health of populations (2019) | Health care |
| `random` negative | The rise of disposable JUUL-type e-cigarette devices (2019) | — |
| `concept` negative | Congenital Adrenal Hyperplasia: Neonatal Mass Screening… Emilia-Romagna, 1980–1995 (1996) | Medicine |
| `concept` negative | Enfortumab Vedotin Antibody–Drug Conjugate Targeting Nectin-4… (2016) | Medicine |
| `concept` negative | Interpretable Decision Sets (2016) | Machine learning, AI |
| `concept` negative | The impact of clozapine on hospital use: a systematic review and meta-analysis (2017) | Medicine |
| `concept` negative | Medical Care, Social Determinants of Health, and Health Equity (2018) | Health care |
| `concept` negative | Optimizing CAR-T Cell Manufacturing Processes during Pivotal Clinical Trials (2019) | Medicine |

Each benchmark has 8 negatives for this query; the `random` list shows 5 of them.

What the example shows:
- **Field, not topic.** Six of the eight `concept` negatives match only through "Medicine" or "Health care".
- **Some `random` negatives are close.** Two of them (ML for music; racial bias in a health algorithm) are arguably as close to the query as any `concept` negative.
- **Duplicate works.** OpenAlex holds two records of the same paper (*Why Most Published Research Findings Are False*: `W2144981148` and `W2331384579`), and the query's reference list cites both. They count as two positives, which inflates n for this query and rewards a method for ranking the same paper twice. Measured by identical normalized titles:
  - 16 of 168 queries (10 of them in test) have duplicate positives: 17 of 1,247 positives (1.4%).
  - No negative duplicates one of its query's positives, in either benchmark, so no cited paper appears as a negative under another id.
  - The effect is small. It is kept as is, matching the reference lists as OpenAlex records them, and reported as a limitation.

### 2026-10-12 — Core test runs complete (preliminary numbers)

The core pass finished in about 3.5 hours: all methods, both benchmarks, 3 seeds, and the position-bias conditions. The extra seeds (3 and 4) are still running. The numbers below are **preliminary**: test split, 118 queries, means over seeds 0–2. CIs and tests come in `05_stats`.

**Position bias confirms the v1 mechanism.** Listwise Llama, same test queries, seed 0:

| Candidate order | `random` MRR / R-prec | `concept` MRR / R-prec |
|---|---|---|
| Positives first (v1's order) | **0.947** / 72.3 | **0.979** / 74.1 |
| Shuffled (v2) | 0.663 / 46.3 | 0.608 / 43.1 |
| Positives last | **0.334** / 30.0 | **0.274** / 19.9 |

With positives first, Llama reproduces (and exceeds) v1's MRR 0.84. With the same candidates reversed, it falls below chance (R-precision about 33%). The model ranks mostly by input position, not content.

**Shuffled results**, R-precision % (`random` / `concept`):

| Method | `random` | `concept` |
|---|---|---|
| Qwen3-Embedding-8B | 87.0 | 80.1 |
| EmbeddingGemma | 85.6 | 78.5 |
| Qwen3 + MiniLM | 85.6 | 78.2 |
| SPECTER2 | 83.5 | 76.6 |
| MiniLM | 83.3 | 75.7 |
| Llama pointwise | 78.8 | 73.9 |
| TF-IDF | 75.3 | 65.4 |
| Qwen3 → Llama (k = 10) | 74.1 | 69.8 |
| Llama + MiniLM | 69.2 | 64.9 |
| BM25 | 68.6 | 63.4 |
| bge-reranker | 67.2 | 58.1 |
| Llama, sliding window | 56.5 | 53.0 |
| Llama, full-list listwise | 45.1 | 42.9 |

What stands out:
- **Pointwise is the best LLM variant.** It is order-independent, beats TF-IDF, and stays below every embedding model.
- **Reranking with Llama lowers Qwen3's own ranking** (87.0 → 74.1).
- **Full-list listwise output is unreliable.** About 37% of answers are partial; with the sliding window, about 1%.

### 2026-10-12 — Test runs, statistics and analyses complete

- **Runs.** `04_test_runs` finished in 4.5 h: 62 run files, all 118/118 queries, 0 errors.
- **Notebooks.** `05_stats` and `06_analysis` ran, and their Findings cells are written. Tables are in `v2/stats/results_<bench>.md`; figures are `05_*` and `06_*` in `v2/figures/`.
- **Fix.** p-values were rounded to 6 decimals and printed as 0; they are now reported unrounded (e.g. 1.8e-19).
- **Final numbers.** They match the preliminary entry. Over 5 seeds, full-list Llama is 43.9 / 42.0 and the sliding window 55.6 / 52.2.
- **Stage-1 recall.** Qwen3's top 10 holds 93% / 89% of references, and its top 20 99% / 98%. So the two-stage drop (−13.0 / −10.4) comes from Llama reranking, not stage 1.
- **Contamination.** Only 1 test query (2 overall) is after Llama 3.2's December 2023 cutoff, so this is reported as not testable.
- **Report.** `research/audit/BEFORE_AFTER.md` compares v1 and v2 claim by claim and method by method. The README is unchanged, pending the user's approval of the v2 results.

### 2026-10-12 — Final checks before review

- **Position-bias CIs.** The position-bias table now has 95% bootstrap CIs. With positives last, MRR is below chance on both benchmarks: 0.33 [0.27, 0.40] and 0.27 [0.21, 0.34], against about 0.56. R-precision is below chance (33.3) only on `concept` (20 [14, 26]); on `random` the CI includes chance (30 [23, 37]).
- **Scope of that experiment.** These conditions change only the candidate order (F1); prompt and text are v2's. So order alone is enough to reproduce v1's MRR 0.84.
- **Corrections.** bge-reranker is below both BM25 and TF-IDF on both benchmarks. Top-1 accuracy with positives first is 94–98%.
- **BEFORE_AFTER.md** now states why v2 reports 118 of the 174 queries: 6 are unusable and 50 are held out for tuning.
- **APP_NOTES.md** records the stage-2 answer for the app.
