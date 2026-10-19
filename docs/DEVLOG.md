# Development log (SWE 599, Spring 2026)

Week-by-week working notes kept during the project. The research summary and final results are in the [main README](../README.md); where numbers here differ, the README is authoritative. The May 2026 final report carries the superseded v1 numbers (see the October 2026 entries).

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

### 2026-10-12 — README updated with v2 results [1452743]

- **Approval.** The user approved the v2 results, and the README was rewritten from them.
- **Correction notice.** The README states that the May 2026 final report and poster carry the superseded v1 numbers.
- **Content.** v2 benchmark description, results table for both benchmarks, the position-bias table, other findings, updated limitations, and reproduction steps.
- **App section.** Unchanged except for a note that stage 2 is under review (see `APP_NOTES.md`).

### 2026-10-12 — Plan documents and open gaps closed (TODO 1.5, 3.2, 7.3, 7.4)

- **Plan documents.** The user's plan and ideas are saved as `research/audit/TODO.md` and `research/audit/IMPROVEMENT_IDEAS.md`. Completed items are ticked, and the original text is kept with status notes added.
- **1.5, data quality** (`audit/data_quality.py`, `audit/DATA_QUALITY.md`).
  - 85 of 1,365 papers (about 6%) carry text that is very likely not their abstract. Examples: author lists, citation strings, journal standfirsts, fragments, a competing-interests note, and two queries whose "abstract" is another paper's title.
  - One paper exists as two query records, one in dev (`W3012006042`) and one in test (`W4247191450`).
  - Without the 11 strong-flagged test queries, no method moves more than about 1 R-precision point and the ranking is unchanged, so nothing was filtered.
- **3.2, stage-1 recall for BM25 and a hybrid.** The hybrid is BM25 + Qwen3 via RRF, computed from the stored runs. At k = 10 (`random` / `concept`): Qwen3 92.5 / 89.0, BM25 80.8 / 76.2, hybrid 89.0 / 84.2. The hybrid's R-precision (78.7 / 72.8) is below Qwen3's.
- **7.3.** Pitch sentences filled where v2 has numbers. Sentences that depend on Phases 4–5 keep their TBDs. While checking, the claim that every method drops 7–10 points on `concept` turned out wrong: the actual range is 1.9–9.9.
- **7.4.** One-page summary in `research/audit/SUMMARY.md`.

### 2026-10-12 — How Llama's listwise output relates to input order

Spearman correlation between each output position and the input position of the candidate placed there, over the shuffled test runs (1,177 outputs with ≥ 5 ranked items, both benchmarks, 5 seeds):

| Pattern | Share of outputs |
|---|---|
| Copies the input order forward (ρ > 0.8) | **50.6%** |
| Reverses the input order (ρ < −0.8) | 6.7% |
| Close to order-independent (\|ρ\| ≤ 0.3) | 29.5% |

The median ρ is **0.98**: the typical listwise answer is a copy of the input list.

Example, test query `W2997681568`, `random` benchmark, seed 0, 12 candidates. Here the model reverses the list:
- with positives first, it outputs `["12","9","8",…,"1",…]` and scores R-precision 0;
- with positives last, it outputs `["12","10","11","9",…,"1"]` and scores R-precision 100.

The same candidates thus get opposite outcomes from order alone. For this query, Qwen3 ranks the 4 positives at 1, 2, 4 and 5 regardless of order.

### 2026-10-12 — PR #1 merged into `main` [e232e49]

- **What.** Branch `v2-audit` (PR senaoz/SWE-599#1) was merged into `main` with a merge commit, `e232e49`.
- **Why a merge commit.** This log cites individual commit hashes; a squash merge would have orphaned them. Later phases keep using merge commits.
- **State after the merge.** v1 stays frozen at tag `v1-results` (614cfb2); v2 notebooks 01–06, the audit documents and the README with v2 results are on `main`. Open work: Phases 4–6 in `research/audit/TODO.md`.

### 2026-10-12 — README: how `random` and `concept` differ

- **What.** Added a section to `README.md` (and a short version to `research/README.md`) that explains the two benchmarks with numbers and two test examples. Requested because the one-line description did not make the difference clear.
- **Numbers** (all 168 queries, recomputed from `v2/eval_sets/`). Share of candidates that share a top-5 OpenAlex concept with their query: positives 73.5%, `random` negatives 29.5%, `concept` negatives 97.7%. Of the matching `concept` negatives, 68.7% match only through a level-0 field such as "Medicine" (positives: 33.2%). 7 of 168 queries have `concept` negatives topped up with random ones.
- **New example.** Test query `W3138513807` (LocusZoom.js): all six `concept` negatives match only through "Computer science".
- **Correction.** The 2026-10-12 note on `concept` negatives says six of the eight `concept` negatives of `W2997681568` match only through "Medicine" or "Health care", and its table lists six. The query has eight; two were missing from the table (2019, team-based continuity; 2020, immune-related adverse events, both "Medicine"). The correct count is **7 of 8**.

### 2026-10-12 — Phase 5 design approved; OpenAlex probe (P0)

- **Design.** `research/audit/PHASE5_DESIGN.md`, approved by the user with all ten recommended decisions. Main points:
  - a citer pool from a per-query title search, published before the query;
  - a candidate corpus of about 10k (all eligible positives plus works cited by at least *m* pool citers);
  - rules R1–R5, each with an ablation; a degree-preserving random graph and a kNN graph as controls;
  - pointwise reranking of the full top-100 list.
- **Why a citer pool.** In the v2 cache, 43.6% of the 1,247 positive slots have a cached citer that is not a query and predates the query (median 0). All such citers are themselves query references, so a graph built from them would be built around the answer key.
- **OpenAlex pricing, checked in the docs.**
  - With no key, the daily budget is $0.10 (`X-RateLimit-Limit-USD: 0.1`, 1,000 credits).
  - A list/filter call costs $0.0001 (1 credit); a **search costs $0.001 (10 credits)**. So without a key the limit is 100 searches a day.
  - `per_page` maxes out at **100**, not 200. The proposal's citer-paging estimates assumed 200 and are corrected here.
  - A free API key gives $1 a day.
- **Probe.** `research/scripts/probe_openalex_p0.py`: 4 dev queries, 7 calls, $0.0052, responses cached in `data/v2/probe/`.
  - A 100-id OR filter works: 99 of 100 cached ids returned (one is no longer in OpenAlex), URL 1,610 chars. 91 of 99 have a DOI.
  - Title search returns 97–8,349 matches per query (first page of 100 used). No query record and no same-title copy of the query appeared.
  - **Positives with at least one pool citer: 7/7, 4/7, 7/7, 3/9 (21 of 30).** The two weaker queries are early COVID (2020-03, only 97 earlier matches) and AI-explanations in health care.
  - A second result page for one query reached no new positive.
  - Corpus size: the 396 pool citers cite 19,468 distinct works; 2,058 are cited by ≥ 2, 739 by ≥ 3 and 370 by ≥ 5.
  - In a seeded sample of 100 such works, 92 are returned and 63 have a title and an abstract.
  - Rough extrapolation to 168 queries, ignoring overlap: m = 5 gives about 15k works, about 10k eligible. *m* will be set from the real P2 counts.
- **Cost of P1–P3:** 168 searches + about 170 list calls ≈ $0.19. That is two days without a key, or one run with a free key.

### 2026-10-12 — Citer pool and candidate corpus (`v2/07_fetch_citers_corpus.ipynb`)

- **Key.** A free OpenAlex API key (daily budget $1) is read from `OPENALEX_API_KEY`. The user keeps it in the macOS Keychain. `src/openalex.request` adds it to requests and strips URLs from every error, so the key cannot reach logs or notebooks; the notebook and log were checked for it.
- **Cost.** 168 searches ($0.168) plus about 145 list calls, about 5 minutes.
- **P1.** 1,726 of 1,733 v2 works are still in OpenAlex. Of the 7 that are gone, 4 are positives.
- **P2, citer pool.** 10,663 distinct works.
  - Median earlier matches per query is 195. 72 queries have fewer than 100 and 5 have none: OpenAlex search behaves like an AND over all title words.
  - 2 query records and 13 same-title copies of queries came back. Five of the copies are earlier versions of the Cochrane review *Electronic cigarettes for smoking cessation* (2012–2018). These make rule R3 concrete.
- **Coverage.** 62% of positive slots (dev 61.9%, test 62.3%) are cited by at least one pool citer that predates the query and is not a query record (same-title copies not yet removed).
- **P3, corpus.** m = 5 was chosen by estimated size only.
  - 12,895 works are cited by at least 5 pool citers (343 of them positives). 71.7% of the returned non-positives have a title and an abstract.
  - Corpus: **9,706 works, 1,176 positives and 8,530 non-positives**, saved in `v2/corpus/corpus_manifest.json`.

### 2026-10-12 — Where the BOUN papers fit (plan addendum)

- **Finding.** BOUN (Boğaziçi) papers are used only in the deployed app and in v1 exploratory checks, never in the v1 cited-paper benchmark or in v2.
  - **App:** `backend/services/seeder.py` extracts BOUN-affiliated authors from `research/data/cleaned/boun.csv` (4,608 papers). That gives 2,671 researchers and 7,803 researcher–paper rows (rechecked with the seeder's logic).
  - **v1 checks:** the Week 1 pairs benchmark and the qualitative checks in `v1/02_similarity_evaluation.ipynb`.
- **Consequence.** The benchmark measures paper → cited papers; the app recommends paper → researcher, with a pointwise stage 2. v2 is evidence about the app, not a test of it.
- **Data check while verifying.** 1,605 of the 4,608 `boun.csv` rows have no abstract (3,003 do), so the app embeds those papers from title and concepts only. The file has not been audited otherwise.
- **Plan.** Added Idea F (researcher-level evaluation with a time split) to `research/audit/IMPROVEMENT_IDEAS.md` and Phase 6B (6B.1–6B.4) to `research/audit/TODO.md`. Nothing is executed yet. Phase 5 is unchanged.

### 2026-10-12 — Fallback citer search and the co-citation graph (`v2/07`, `v2/08`) [e14f50c, 5952b8b, 02acdbf]

- **Decisions (user, 2026-10-12).** All three recommendations were approved:
  1. a second citer search for low-result queries;
  2. earlier versions of living reviews count as query duplicates;
  3. drop the 5 lost positives from the labels.
- **Fallback search** [e14f50c]. 72 queries had fewer than 100 title-search results. They got a second search on the first 6 content words of the title (72 searches, $0.072).
  - The pool grew from 10,663 to 13,572 citers, and positive-slot coverage from 62% to 64.5%.
  - m = 5 was kept as fixed before the fetch. Real eligibility was 71.5% (P0 estimate 63%), so the corpus came out at 12,096 records, not 10k.
- **Graph code** [5952b8b]. `src/cograph.py` holds canonicalization, query-duplicate detection, the citer × document graph with per-query rule masks (R1–R5 plus canary), co-citation scores and Curveball rewiring.
  - `research/tests/test_cograph.py` has 11 tests. pytest 9.1.1 was installed (new dependency, approved).
- **R3 rule, settled by inspecting every match.**
  - Token-overlap near-titles matched different papers, e.g. *On airborne transmission and control of SARS-CoV-2* for the query *Airborne Transmission of SARS-CoV-2*.
  - The final rule is: DOI, exact title (any year), or digit-free character similarity ≥ 0.9 **with a shared author id**.
  - The author condition is not applied to exact titles. A 2012 record titled *Electronic cigarettes for smoking cessation.* shares all 10 of the 2020 query's references but no author id, and a date-only rule would have allowed it.
  - Result: 20 pool works duplicate a query (12 title, 7 near-title, 1 DOI), and 3 query records are in the pool.
- **Notebook 08** [02acdbf].
  - **Canonicalization:** 12,096 records → 11,968 works (119 duplicate groups); 11,967 are eligible candidates.
  - **Labels:** 1,247 → 1,219 positive slots (5 dropped, 9 merged). Dev drops `W3012006042` (decision 6) and `W4388291555` (2 positives left), giving 48 dev / 118 test queries.
  - **Graph:** 13,743 citer rows, 127,908 edges.
- **Reachability** (share of test positives that an allowed citer cites):
  - all rules: 63.4%;
  - R3 off: 65.3%; **R4 off: 68.2%**; R5 off: 63.5%; R3–R5 off: 70.1%;
  - canary: 100%, as required.
- **Membership asymmetry.** Positives have a median of 2 pool citers (33.5% have none); non-positives have a median of 7, by construction. A degree-only probe is planned for notebook 09.

### 2026-10-12 — Checkpoint A: leak diagnostics before the rule set is signed off

Ad hoc checks on the notebook-08 graph. They will move into notebook 08 together with whichever rule the user chooses.

- **High-overlap citers.** Under all rules, 189 allowed citers (57 dev, 132 test) cite at least half of a query's positives. Most are legitimate (topic reviews, same-author earlier work), but two leak types show up:
  1. **Imprecise dates.**
     - 3,227 of 13,572 pool citers (24%) are dated YYYY-01-01, which is often a year-only date. 69 of the 189 high-overlap citers carry such dates; for example, COVID papers "dated" 2020-01-01 pass R4 for queries from February 2020.
     - 3,479 citer rows cite a work dated after their own date, which is impossible if both dates were right.
     - Reachability of test positives under each date rule:

       | Date rule | Test reachability |
       |---|---|
       | current | 63.4% |
       | Jan-1 dates moved to Dec-31 | 59.5% |
       | effective date ≥ latest cited work's date | 57.7% |
       | both | 54.7% |
       | 365-day margin | 34.4% |

       Citers with at least 50% overlap fall from 132 to 66 under "both".
  2. **The same work under a different title.** The query *NeRF* (CACM, 2021) has the ECCV paper *NeRF: Representing Scenes as Neural Radiance Fields…* (two records) as a citer. The query *"How do I fool you?"* has its preprint as a citer. Title containment plus a shared author also catches unrelated papers (*Mip-NeRF*, *NeRF in the Wild*, an e-cigarette RCT), so it cannot be an automatic rule.
- **Citer duplicates.** Pool citers are not deduplicated among themselves: canonicalization would merge 13,572 into 13,464, so 108 rows double-count co-citation edges.
- **Checked and fine.** The dropped positive `W3012048021` is in no duplicate group, so the label was not lost through canonicalization.
- **Assumption, not verified.** `fetch_works` treats any id missing from a successful response as permanently gone. 819 of 17,275 (4.7%) is in line with the ~5% seen in P0.

### 2026-10-12 — Checkpoint A decisions applied (`v2/08_build_corpus_graph.ipynb`)

- **Decisions (user).** All three were approved:
  1. conservative citer dates for R4;
  2. a manual, reviewed list of query duplicates with different titles;
  3. merging duplicate citers.
- **Code.** `src/cograph.py` gains `effective_day` (a YYYY-01-01 date counts as Dec 31; a citer is never earlier than the latest known date among its references) and `merge_duplicate_citers`. There are now 14 unit tests, all passing.
- **Results** (test / dev reachability of positives):
  - **all rules: 54.7% / 53.0%** (62.9% / 62.4% with recorded dates);
  - R4 off: 68.1% / 67.0%;
  - canary: 100%.
- **Graph.** 13,569 pool records → 13,461 citer rows; 16 query-duplicate rows; 126,377 edges. 5,097 pool rows got a later date than recorded.
- **Remaining high-overlap citers** (≥ 50% of a query's positives): 66 test and 30 dev rows, at most 80%, mostly topic reviews and commentaries. No exact copies are left.
- **Meaning.** About 45% of test positives have no allowed citer, so co-citation expansion can recover at most about 55% of them. The data-quality finding stands on its own: a quarter of pool citers carry January-1 dates, and 5,097 rows had to move later.

### 2026-10-12 — Full-corpus first stage (`v2/09_full_corpus_retrieval.ipynb`) [5bd3b69, c0a7c1f]

- **What.** Every method ranks the whole 11,967-work corpus for the 166 Phase 5 queries.
  - Candidates are the works published before the query, plus its own positives; 13 corpus records that duplicate a query are excluded for that query.
  - Text and methods are as in v2, plus BM25 + Qwen3 RRF, a degree-only probe and a random ranker.
  - New module: `src/retrieval.py`.
- **Runtime.** Qwen3-8B embedded about 10,300 corpus texts in about 50 minutes (322 batches at about 9.4 s), after a 500-text timing probe (0.31 s/text). Everything else took minutes.
- **Results** (test, 118 queries, recall@100 [95% CI]):
  - Qwen3 **64.0 [58.7, 69.4]**, EmbeddingGemma 60.6, RRF 60.2, SPECTER2 57.5, MiniLM 55.4, TF-IDF 45.3, BM25 38.7;
  - degree probe 2.4 [1.1, 3.9], random 1.3.
  - Qwen3: nDCG@10 0.340, MRR 0.609, R-precision 25.1% (87.0% on the fixed v2 pools).
- **Tests** (Holm). Qwen3 vs EmbeddingGemma on recall@100 is not significant (p_holm = 0.11); Qwen3 beats all others. RRF hurts Qwen3 (−3.9 points recall@100, −0.065 nDCG@10), as in v2.
- **Membership check.** The degree-only probe is near random, so adding positives regardless of degree (decision 3) gives no exploitable signal. On the membership-symmetric positives (424 with ≥ 5 pool citers), Qwen3 recall@100 is 73.4% vs 63.1% on all positives of the same queries.
- **Headroom for expansion.** 315 of 855 test positives are outside Qwen3's top 100; 151 of them (47.9%) are reachable through an allowed citer.

### 2026-10-13 — Graph expansion with controls (`v2/10_graph_expansion.ipynb`) [d34f8fa, 237e399, 867d11f]

- **What.** GRIT-style expansion of Qwen3's full-corpus top 100: seeds = top t; the bottom fraction b is replaced by the seeds' co-citation neighbours under all leakage rules.
  - t, b and the normalization were chosen on dev (48 queries).
  - Controls: 5 Curveball random graphs, a Qwen3 kNN graph, rule-by-rule ablations and the canary.
  - Also an adaptive LADR-style run with BM25 seeds over a Qwen3 kNN graph.
  - New module `src/expansion.py` with 5 unit tests (19 tests in total). No model or API calls; the whole notebook runs in about 35 s.
- **Dev choice.** Raw counts, t = 5, b = 10%: +1.7 points recall@100 on dev. Larger b hurts (down to −5.2).
- **Test** (118 queries, recall@100 difference from Qwen3's 64.0, paired bootstrap CI, Holm-corrected Wilcoxon):

  | Condition | Difference |
  |---|---|
  | Co-citation, all rules | **+0.8 [−0.4, +2.1]**, p = 0.32 (Holm 1.0) |
  | Random graphs | −0.5 to −0.9 |
  | kNN graph | +0.3 [−0.6, +1.3] |
  | R3 off | +0.8 |
  | R4 with recorded dates | +1.0 |
  | R4 off | +1.1 |
  | R5 off | +1.0 |
  | **Canary** | **+5.8 [+3.6, +8.2]** (Holm p = 1.6e-4) |
  | LADR (k = 32) | −1.7 [−4.1, −0.0], scoring 12.5% of candidates |

- **Attribution.** 20 of the 548 positives in the expanded lists (3.6%) entered through the graph, i.e. 6.3% of the 315 Qwen3 missed. The replacement pushed 8 positives out.
- **Reading.** With a strong dense first stage and a leakage-controlled graph, co-citation expansion gives a small, non-significant recall gain. The canary shows the method works when the signal is present.

### 2026-10-13 — System overview diagram updated with Phase 5

- **Merge.** `origin/main` (which had gained the system overview diagram, 31bc5cc) was merged into `v2-phase5` with a merge commit (7ad061c).
- **Diagram.** `docs/figures/system_overview.svg` gains a Phase 5 row: notebooks 07–10 and a results box.
  - Qwen3 recall@100 64.0%; co-citation expansion +0.8 [−0.4, +2.1], not significant.
  - Random graph −0.8, kNN graph +0.3, canary +5.8.
  - Reachability 54.7% (62.9% with recorded dates).
  - The two leak findings.
- **Also changed.** The deployed app moves to row 5. The BOUN note now says 1,605 of its 4,608 papers lack an abstract. The evidence arrow points to notebook 11.
- **Rendering.** Checked in the browser.
- **Caveat.** The README embeds this diagram, so the Phase 5 numbers now appear on the README page. The README text itself is unchanged.

### 2026-10-13 — End-to-end pointwise reranking (`v2/11_end_to_end.ipynb`) [eece963, 8f23f84]

- **What.** Pointwise Llama 3.2 3B (the v2 prompt and text, temperature 0, logprob score) scores every candidate in two top-100 lists per query: Qwen3-Embedding's list and the co-citation expanded list from notebook 10.
  - The final score is α · Llama + (1 − α) · Qwen3-Embedding, both min-max normalized within the list. α was chosen on dev.
  - New module `src/rerank.py` with a per-(query, document) score cache, plus 3 unit tests (22 tests in total).
- **Run.** 17,939 pairs (108 per query), all status ok.
  - The first background run stopped when the previous Claude session ended, after 3,052 pairs.
  - The resumed run reused the cache and scored the remaining 14,887 in 87.4 min (0.352 s per call, against 0.193 s in v2).
  - A rerun to fix the results table (it rounded p-values to 0.000) made no new calls.
- **Results** (test, 118 queries):
  - **Llama alone**: nDCG@10 0.340 → 0.175 (−0.164 [−0.204, −0.126], Holm p = 3.1e-11); R-precision 25.1% → 14.3%.
  - **Fused** (α = 0.1): −0.004 [−0.009, +0.001], p = 0.24.
  - The expanded lists give the same picture; the fused ranking puts no graph-recovered positive into the top 10 or 20.
  - Within-list AUC: Llama 0.663 vs Qwen3-Embedding 0.761.
- **Docs.** Results were added to both diagrams and to `APP_NOTES.md`. `TODO.md` ticks 5.8 and 5.9 for Llama; Qwen3-Reranker-4B (downloaded, revision 22e6836, 8.04 GB) is still to run.
- **README.** The superseded v1 poster was removed and the correction notice no longer mentions it [cd8cdd0, 333325e]. Both were pushed to `origin/v2-phase5` with the senaoz token, because the active gh account is sena-maesta.

### 2026-10-14 — Qwen3-Reranker-4B as the second stage (`v2/12_qwen3_reranker.ipynb`) [1071f25, 0193bab, e55008c, 97b663f]

- **Download** (user-approved). `Qwen/Qwen3-Reranker-4B`, revision 22e6836, 8.04 GB. File sizes match the Hub; the SHA-256 of shard 1 matches its LFS id.
- **Check** (`scripts/check_qwen3_reranker.py`, 17 dev pairs).
  - Model-card reference implementation, fp16 vs fp32: max difference 0.006, Spearman 1.000, no NaNs.
  - sentence-transformers CrossEncoder vs reference: max difference 0.021, Spearman 0.998.
  - Speed per pair: reference fp16 0.54 s, sentence-transformers 0.79 s, fp32 1.11 s.
  - **Decision:** the reference implementation in fp16, batch 8 (batches 4, 8 and 16 differed by less than 0.02 s per pair).
  - The instruction was fixed before any result: "Given the title and abstract of a scientific paper, retrieve papers that it cites".
- **Run.** 17,939 pairs, all ok, in 256.9 min (0.859 s per pair). Swap was nearly full (25.8 of 26.6 GB) late in the run, which slowed it.
- **Results** (test, 118 queries).
  - Within-list AUC: Qwen3-Reranker 0.824, Qwen3-Embedding 0.761, Llama 0.663.
  - Dev α = 0.8 (nDCG@10 0.344 → 0.393 on dev).
  - **Fused**, Qwen3-Embedding list:
    - nDCG@10 0.340 → 0.360 (+0.021 [+0.001, +0.041], p = 0.044, Holm 0.22);
    - R-precision 25.1 → 28.3 (+3.2 [+1.2, +5.2], p = 0.008, Holm 0.040);
    - MRR 0.608 → 0.629.
  - **Reranker alone:** +0.002 nDCG@10, not significant.
  - **Expanded list, fused:** +0.015 nDCG@10 (not significant), R-precision +2.7 (Holm 0.083). No graph-recovered positive in the fused top 10.
- **Reading.** A trained reranker, unlike the small general LLM, gives a modest gain when fused with the embedding score. The pretraining-contamination caveat applies.
- **Docs.** Diagrams, `TODO.md` and `APP_NOTES.md` were updated.

### 2026-10-14 — README Phase 5 section and a consistency pass over all documents [55e2a45]

- **README.** The user approved the Phase 5 numbers and asked for a README section (55e2a45). It sits after the v2 results, with figures 09 and 12. The limitations, next steps and app description were updated to match. This supersedes the 2026-10-13 note that "the README text itself is unchanged".
- **Consistency pass** (user request). Three read-only agents compared every document and every notebook's Findings with their sources: notebook outputs, stats files, code and config. Each finding was then checked by hand.
- **Fixes in the documents:**
  - **`README_APP.md`.** The app uses `qwen3-embedding` (not nomic). Stage 1 keeps the top 10 researchers (not 20). Stage 2 sees the researcher's top 5 papers (not 3) and answers `IRRELEVANT <score>`. There are about 7,800 researcher–paper rows (4,608 papers). The v1 research section and its invalidated hit rates were replaced by links. Source: `backend/config.py`, `backend/services/matching.py`.
  - **`APP_NOTES.md`.**
    - Jan → llama-server.
    - "v1 found" → "the audit (F1, F2) found".
    - Graph work is Phase 5, not Phase 4.
    - The 2026-10-13 entry said "top-3 papers"; it is top 5 (`RAG_CONTEXT_PAPERS`).
    - Superseded entries are marked; the ideas are rewritten.
  - **`research/README.md`.**
    - EmbeddingGemma runs in-process (its GGUF lacks the Dense layers); the stray ini section is removed.
    - The tree and intro now cover notebooks 07–12, `tests/` and `scripts/`.
    - `run.py` is gone, `PHASE5_DESIGN.md` is added, and the duplicated `random`/`concept` paragraph is replaced by a link.
    - The seed spread lives in the notebook, not in `v2/stats/`.
  - **`README.md`.** Repository tree updated; Phase 5 spans notebooks 09–12; MiniLM is within 3.7 / **4.3** points (the mean per-query difference); SPECTER2 vs MiniLM Holm p ≥ **0.84**.
  - **Other files.**
    - `SUMMARY.md`: Phase 5 paragraph, limitations and next steps.
    - `BEFORE_AFTER.md`: PR #1 merged; Holm p ≤ 3.4e-19.
    - `TODO.md`: status notes; 14 (22) tests; 5.9 attribution for both rerankers; CHECKPOINT 5; 7.3.
    - `IMPROVEMENT_IDEAS.md`: Idea C and full-corpus Idea D status; Phase 5 pitch sentence. It records that expansion does *not* lift end-to-end MRR, contrary to the original sentence.
    - `PHASE5_DESIGN.md`: 174 excluded query records (not 168); dev 48/118; notebook 12 and `rerank.py`.
    - `AUDIT.md`: 1,811 reference slots = 1,729 distinct works; the Ollama header note is moot.
    - System diagram: the Phase 5 row is labelled 07–12.
- **Fixes in notebook Findings** (markdown only, no reruns):
  - 03: Qwen3 at 81–89%.
  - 03: the "199 of 200" and "40–52%" claims were checked against the dev run files and are correct; the source is now cited.
  - 03: the `concept` statement is qualified.
  - 05: p ≥ 0.84, 4.3, Holm p ≤ 3.4e-19.
  - 06: top-1 at 94–97%.
  - 07: six Cochrane versions (not five).
  - 09: recall@5 was never reported; the dev wording is corrected.
  - 10: reachability 55.1–70.1%.
  - 11: Holm 0.48 added.
  - 04: a Findings cell was added (it had none).
- **Corrections to earlier entries in this log:**
  - 2026-10-12 "Scope of the test runs": 13 methods, not 12.
  - 2026-10-12 "Test runs, statistics and analyses complete": final Llama + MiniLM is 69.0 / 63.7 (preliminary 69.2 / 64.9) and Qwen3 → Llama 74.0 / 69.7 (preliminary 74.1 / 69.8). The other numbers match.
  - 2026-10-12 "Fallback citer search and the co-citation graph": 23 query duplicates once the manual list of Checkpoint A is included (20 before).
  - First-stage MRR of Qwen3 is 0.609 over the full candidate ranking (notebook 09) and 0.608 within the top-100 list (notebooks 11–12). The two are computed over different lists.
- **Left as is (intentional overlap):** the README findings vs SUMMARY, the README results vs BEFORE_AFTER, and dated status notes that repeat DEVLOG facts.

### 2026-10-14 — PR #3 merged into `main` [73b07d3]

- **What.** Branch `v2-phase5` (PR senaoz/SWE-599#3, 56 commits) was merged into `main` with a merge commit, `73b07d3`.
- **Why a merge commit.** As for PR #1: this log cites individual commit hashes, which a squash merge would orphan.
- **State after the merge.** Phase 5 notebooks 07–12, `src/corpus.py`, `cograph.py`, `retrieval.py`, `expansion.py`, `rerank.py` and the 22 unit tests are on `main`. Open work: Phase 6B (next), Phase 4 and Phase 6 in `research/audit/TODO.md`.

### 2026-10-14 — MTPLX (Qwen3.8-27B) as a candidate stage-2 model for the app: setup and smoke test

- **What.** The user chose to replace the app's stage-2 Llama 3.2 3B with MTPLX serving `Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`. Stage 1 keeps Ollama `qwen3:embedding`. No `backend/` code is changed yet.
- **Server.** `mtplx serve` on `127.0.0.1:38757` (bound to localhost; port picked at random below the macOS ephemeral range), with an API key. The key lives in the macOS Keychain (`mtplx-api-key`) and in a mode-600 key file for the server; the server log is mode 600 because MTPLX prints the key at start-up. The first key was printed to the session once, so it was rotated before any test.
- **Memory.** The MTPLX desktop app had started its own server on port 8000 with the same 19.3 GiB model; with both loaded, requests were refused with HTTP 507 (2.8 GiB free, swap 17.7 of 18.4 GB). The port-8000 server was stopped (user decision).
- **Smoke test** (scratch scripts, not a benchmark): the app's prompt and parsing copied verbatim from `_llm_generate`, sent as one user message to `/v1/chat/completions`.
  - 10 true pairs (a BOUN researcher and a cached external work they later cited; context = their 5 most TF-IDF-similar papers published before the citing paper) and 10 random-researcher pairs on the same works.
  - Thinking off: 0 of 20 answers were `RELEVANT`, so the app would drop every researcher. Median 6.9 s per call.
  - Thinking on: 3 of 10 true pairs and 0 of 10 random pairs were `RELEVANT` (all at 0.45). Median 31.1 s per call; the reasoning goes to a separate field and the answer line stays parseable.
  - On 20 other pairs (Phase 5 works with TF-IDF-close or random researchers) with thinking off, 5 of 20 answers started with prose instead of the verdict; the app's parser maps those to 0.0.
  - The number after `IRRELEVANT` still ranks: mean 0.135 on true vs 0.045 on random pairs (thinking off), but the app discards it.
- **Implication.** With the current prompt and parser, the 27B model would act as a near-total filter. Any switch needs a prompt/parser change and must be evaluated in Phase 6B before deployment; 20 pairs are a smoke test, not evidence.

### 2026-10-14 — App stage 2 moved to MTPLX with a score-only prompt (branch `app-mtplx-stage2`) [e8b9cca, d926d4c, 02a8429, fc54e0a]

- **What.** Stage 2 of the app calls Qwen3.8-27B on the local MTPLX server (`127.0.0.1:38757`, OpenAI `/v1/chat/completions`, temperature 0, thinking off by default) through a new `backend/services/llm.py`. Stage 1 is unchanged (Ollama `qwen3:embedding`).
- **Why.** The smoke test with the old prompt (entry "MTPLX (Qwen3.8-27B) as a candidate stage-2 model", on branch `v2-phase6b`) showed the old `RELEVANT/IRRELEVANT` prompt plus first-token parser would drop nearly every researcher.
- **Changes.**
  - Prompt asks for one number in [0, 1], with no example value.
  - Parser drops `<think>` blocks and accepts only a single number in [0, 1] on the last line; otherwise the Stage 1 score is kept and the reply is logged. 20 unit tests in `backend/tests/test_llm.py`.
  - The cosine `MATCH_THRESHOLD` no longer applies to LLM scores; `LLM_MIN_SCORE` (default 0.0) is the LLM's own cut-off, to be tuned in Phase 6B.
  - Matches are labelled `qwen+<LLM model id>` instead of `qwen+llama`.
- **Check** (same 20 pairs as the smoke test, through `score_researcher`, thinking off): 20 of 20 replies parsed. True pairs scored 0.2 (5), 0.1 (1) and 0.0 (4); random pairs all 0.0. Within a pair, the true researcher scored higher in 6 of 10 and tied in 4. Median 7.75 s per call. Scores are coarse (only 0, 0.1, 0.2 seen), so many ties; this is a smoke test, not an evaluation.

### 2026-10-14 — Stage-2 prompt variants on MTPLX (scratch experiment, not a benchmark)

- **Pairs.** 159 cached works from 2018 on that a BOUN researcher cited (Phase 5 caches, no new fetch). For each work: the earliest citing researcher (context = their 5 most TF-IDF-similar papers published before the citing paper) and a hard negative (the non-citer with the highest TF-IDF match, same date cut-off). Split by sha256 of the work id, 30 dev and 30 holdout works, fixed before any run. The 60 work ids are in `research/audit/prompt_dev_works.json` and must be excluded from the Phase 6B test set.
- **Variants** (thinking off, temperature 0): P0 the current score-only prompt; P1 a 0–100 rubric with a "method, tool or dataset" band and a no-abstract note; P2 P1 with longer text (1,500 / 400 characters instead of 400 / 200).
- **Metric.** Share of pairs where the citer scores above the hard negative (ties count 0.5); 95% bootstrap CIs over works; paired Wilcoxon.
- **Dev** (30 pairs): P0 0.533 [0.400, 0.667], P1 0.600 [0.467, 0.717], P2 0.567 [0.433, 0.683]. P1 − P0 +0.067 [−0.033, +0.167], Wilcoxon p = 0.2059032107320683; P2 − P0 +0.033 [−0.083, +0.150], p = 0.5637028616507731. P1 was chosen on dev.
- **Holdout** (30 pairs, run once): P0 0.617 [0.467, 0.750], P1 0.683 [0.533, 0.833]; P1 − P0 +0.067 [+0.000, +0.150], 6 pairs differ, Wilcoxon p = 0.10247043485974945. Not significant.
- **Score scale.** All 120 dev replies and all 120 holdout replies parsed. P1 replies cluster on band values (dev citers: 0 ×8, 25 ×12, 45 ×8, 35 ×1, 65 ×1), so ties stay common (14 of 30 dev pairs) and most cited works are rated "same broad field, different topic".
- **Reference.** The TF-IDF stage-1 proxy ranks the citer above the negative in 4 of 30 dev and 5 of 30 holdout pairs, but the negatives were chosen to be TF-IDF's hardest, so this is not a fair comparison.
- **Speed.** Median 7.6–8.9 s per call on dev and 3.6–4.4 s on holdout (less memory pressure later in the run).

### 2026-10-14 — Findings from the MTPLX stage-2 work, and a change of direction

- **Findings** (details in the three entries above):
  1. The app's old `RELEVANT/IRRELEVANT` prompt with its first-token parser would drop nearly every researcher on Qwen3.8-27B; with thinking off, some replies also open with prose and are silently mapped to 0.
  2. A score-only prompt and a strict parser fix the parsing (240 of 240 replies parsed), but scores stay low and coarse (band values such as 0, 25, 45 on a 0–100 rubric).
  3. Prompt changes give small, non-significant gains: P1 − P0 +0.067 on both dev and holdout (holdout CI [+0.000, +0.150], Wilcoxon p = 0.10247043485974945); longer text did not help.
  4. Under the rubric, most citers of a work rate it "same broad field, different topic". Citation labels and topical relevance diverge: people cite methods, tools and background as well as topical work.
  5. The read path filters matches with the cosine `MATCH_THRESHOLD` (`backend/routers/papers.py`, `min_score` default 0.3), so LLM-scale scores would hide every new match in the feed. Branch `app-mtplx-stage2` must not be merged as is.
  6. Cost: 3.6–8.9 s per call with thinking off, about 31 s with thinking on, against about 0.35 s for Llama 3.2 3B.
- **Decision (user, 2026-10-14).** Do not dig further into the citation-vs-topical-relevance gap (e.g. citation intents or graded citation labels as the fix). Explore alternative ways to evaluate and design the app's matching instead. Backend changes on `app-mtplx-stage2` are on hold; the Phase 6B design (citation-based positives) is paused pending this discussion.

### 2026-10-15 — The app's task, restated (user correction)

- **Task.** A logged-in user sees recent papers from the institutions they follow; under each paper the app lists BOUN researchers, with their matching papers. Relevance means "this BOUN researcher works on what this paper is about" (topical expertise). It is not "the researcher would cite it" (citation labels; Idea F / Phase 6B as first written) and not "the researcher wrote it" (the authorship-based expert-finding idea of 2026-10-14, which used BOUN papers as queries and was dropped).
- **Feedback matches this unit.** `paper_feedback` stores `is_relevant` per (user, paper, researcher), i.e. a judgment on exactly one listed researcher under one paper.
- **Data check.** `boun.csv` has 311 papers with a co-author from the v1 followed-institution list (lineage ids in `v1/01`), 162 of them from 2023 on.

### 2026-10-15 — BOUN works refetched from OpenAlex (`research/scripts/fetch_boun_openalex.py`)

- **What.** All works matching the v1 filter (`authorships.institutions.lineage:i4405392, type:article, publication_year:2020-`), cursor-paged into `research/data/v2/boun/works.jsonl` (gitignored), with topics and keywords added to the fields. 1 count call + 61 list calls (about $0.006) and 1 diagnostic call. `research/data/cleaned/boun.csv`, which the app seeds from, is unchanged.
- **Size.** 6,001 works (count call: 6,001), dates up to 2026-10-14. Language tags: en 5,336, tr 293, lv 231, none 114, other 27.
- **Language tags are unreliable.** The `lv` records are English ATLAS papers (e.g. "Combined measurements of Higgs boson production and decay…"); filtering on `language == "en"` would drop them.
- **Against `boun.csv`** (English subset, 5,336 works): 3,895 works in both, 1,441 only in the refetch, 713 only in `boun.csv` (708 of them absent from the refetch, 5 now tagged non-English).
- **Why works disappeared.** A probe of 100 of the 708: 12 no longer exist (deleted or merged); of the 88 returned, 77 are still BOUN-affiliated but most are no longer typed `article` (conference-paper 52, editorial 4, preprint 5, review 3, book-chapter 3, book-review 3, erratum 3, conference-abstract 2, letter 1, retraction 1; article 11). So `boun.csv` holds conference papers but also editorials, errata and a retraction notice as "researcher papers".
- **Abstracts.** Missing in 1,235 of 5,336 English works (76.9% coverage), against 1,605 of 4,608 in `boun.csv` (65.2%). On the 3,895 common works, 381 abstracts were recovered and 15 lost.
- **Other checks.** Topics present on 100.0% and keywords on 99.9% of English works; 47 common works changed date; 10 duplicate DOIs and 34 duplicate normalized titles; 2 retracted works.

### 2026-10-15 — BOUN data rebuilt and audited (TODO 6B.1) [d4258c0, 3838637, 4367ce4, 58f9bb6, de90395, fbdf76d, 9d9ab7c, 173619a, 273a426]

- **Decisions (user, 2026-10-15).** Keep work types broad (research outputs, not only articles); do not use the OpenAlex language tag; try Crossref and Semantic Scholar for missing abstracts if free; **no human evaluation in the project** (TODO 4.5, 6.2–6.3 dropped); make the BOUN data pushable.
- **Fetch.** All BOUN works from 2020 on, every type: 8,287 records (count call by type, then 83 list calls). List records stop at 100 authorships, so the 1,072 such records were refetched one by one (single-work calls cost $0 per the response headers; about 23 min); 1,064 of them have BOUN authors, 7,400 BOUN authorships in total. OpenAlex spend today about $0.016.
- **Language.** A stopword rule on title and abstract (`src/boun_data.language_flag`) replaces the OpenAlex tag. All 324 OpenAlex-`tr` records were reviewed by hand: 229 Turkish, 57 bilingual, 33 English, 4 other, 1 empty. The rule was fixed twice during review (Turkish-only letters for all-caps titles; a Romance-language class, since "de"/"da" are not only Turkish).
- **Abstracts.** 1,868 DOIs without an OpenAlex abstract: Crossref returned 115 abstracts (public pool, 1 request/s), Semantic Scholar 503 (anonymous batch endpoint, after 429 back-off); 606 distinct works in total. Their text stays in the gitignored cache because publisher copyright may apply and the repository is public; only `abstract_source` is committed.
- **Clean table** (`research/data/boun/`, Git LFS): 7,985 research-type records, 163 merged as duplicates (mostly preprint/published pairs; 8 sampled groups checked by hand), **7,822 works**; text for 6,585 (84.2%); 4,639 BOUN author ids and 18,597 researcher–work rows; 1,302 researchers have only 100+-author works. Data card: `research/audit/BOUN_DATA.md` (all numbers generated by `research/audit/boun_data_report.py`).
- **Against `boun.csv`.** 4,456 works in both, 152 only in `boun.csv` (97 no longer returned by the BOUN filter, 55 dropped as non-research types), 3,529 only in the new data. `boun.csv` cuts author lists at 100 (223 records). The app still seeds from `boun.csv`.
- **Docs.** `TODO.md` (6B.1 done; 6B paused; 4.5, 6.2–6.3 dropped), `IMPROVEMENT_IDEAS.md` (Idea F update; the stage-2 context is 5 papers, not 3), `SUMMARY.md` (limitations, next steps), `research/README.md` (tree), `APP_NOTES.md` (seed data issues).

### 2026-10-15 — Correction

- "BOUN data rebuilt and audited": OpenAlex spend was about **$0.015**, not $0.016 (the rate-limit header showed $0.9853 of the $1 daily budget left after all list calls; single-work calls were $0).

### 2026-10-15 — BOUN researcher names, README, MTPLX stopped

- **Names.** The 1,072 works with 100+ authors were refetched one by one, this time keeping each BOUN author's display name (`full_authors_named.jsonl`; same 1,072 works and identical BOUN id lists as the first pass; $0, about 23 min). New `research/data/boun/researchers.csv.gz` (id, name, number of works): all 4,639 researchers named, against 1,083 without a name before. The other data files are unchanged in content.
- **README.** Limitations and next steps updated for the no-human-evaluation decision, the restated app task and the new BOUN data [2e40480].
- **MTPLX** server on port 38757 stopped (user request); `mtplx stop` did not recognise it, so the process was terminated directly.

### 2026-10-15 — Notebook 13 and a BOUN attribution fix (`v2/13_boun_data.ipynb`)

- **What.** Exploration notebook for the cleaned BOUN data (pandas; overview, researchers, a `profile()` helper, attribution checks, quality flags), run with papermill.
- **Finding 1: misattributed collaborations.** 6 large works (2 ATLAS, 4 BESIII; 491–2,881 authors) list 77–370 BOUN authors each, against a median of 6 per large work: OpenAlex attached the BOUN affiliation string to the wrong authors. The build now keeps a BOUN author on such a work (more than 20 BOUN authors) only if another work confirms them (`boun_attribution_suspect`). 12 of 1,003 were confirmed; **991 researchers were dropped**. Corrects the "BOUN data rebuilt and audited" and "BOUN researcher names" entries: researchers 4,639 → **3,648**, researcher–work rows 18,597 → **17,198**, collaboration-only researchers 1,302 → **311**. Works are unchanged (7,822).
- **Finding 2: raw-affiliation check.** BOUN addresses appear with HTML entities (`Bo&#x011F;azi&#x00E7;i`) and PDF splits (`Bogazic ¸i`); `src.boun_data.names_boun` normalises them. Then 78 of 12,008 small-work BOUN authorships (0.65%) do not recognisably name Boğaziçi (34 researchers rest only on them): a mix of mangled spellings and real OpenAlex errors (e.g. a Koç University address). Kept, not filtered. The first version of this check (483 authorships, 107 researchers, reported in chat) was wrong for the encoding reason.
- **Finding 3.** OpenAlex splits some people into two author ids (e.g. "Ismail Okan Atakisi", 214 works, and "I. O. Atakisi", 213).
- **Tests.** 27 pass (2 new: encodings, suspect collaborations).

### 2026-10-15 — PR #4 merged into `main` [f802d55]

- **What.** Branch `v2-phase6b` (PR senaoz/SWE-599#4, 37 commits) was merged into `main` with a merge commit, `f802d55`.
- **State after the merge.** The cleaned BOUN data (`research/data/boun/`, Git LFS), its data card (`research/audit/BOUN_DATA.md`), notebook `v2/13_boun_data.ipynb`, `src/boun_data.py` with tests (27 in total), the restated app task and the no-human-evaluation decision are on `main`. Branch `app-mtplx-stage2` (stage 2 on MTPLX) stays unmerged: its read path still filters matches at the cosine threshold 0.3. Open: an evaluation design for the restated task, with the stage-1 field ablation on the new data.

### 2026-10-15 — Stelmakh et al. gold-standard expertise data downloaded and profiled

- **Why.** Citation labels measure "would cite", not topical expertise; a human-labelled, public expertise dataset lets the paper test which conclusions survive a change of label without running our own human study.
- **What.** Sparse clone of `niharshah/goldstandard-reviewer-paper-match` at `00296730` into `research/data/external/goldstandard/` (gitignored, 144 MB; full-text folders, about 2.5 GB, skipped). Data card: `research/audit/GOLDSTANDARD_DATA.md`; numbers from `research/audit/goldstandard_report.py`.
- **Findings.** 58 researchers, 477 self-rated expertise scores (1–5), 463 papers (458 of 462 CS), profiles of up to 20 own papers. Ranking direction is papers-per-researcher, not researchers-per-paper (13 papers have two raters), so cross-researcher calibration stays untested. Published baseline losses recomputed from the repository's prediction files: SPECTER2 with max over profile papers 0.221, o1-mini 0.245, Claude 3.5 Sonnet 0.311, constant 0.500 (to check against the paper's Table 3).

### 2026-10-15 — Matching design draft (`docs/MATCHING_DESIGN.md`)

- **What.** Design doc for the app's target matching flow (persistent per-work BOUN index, streamed external papers, researcher-level aggregation, no LLM stage 2, calibrated cut-off, versioned matches and feedback). Draft for review; no code, schema or embedding change.
- **Findings from the code read.** pgvector cannot ANN-index 4,096-dim vectors (exact scan is fine at 7,822 works); `researcher_papers` embeds a work once per BOUN co-author; matches and feedback carry no model version; the read path filters at cosine 0.3 independently of the job; works with a followed-institution co-author can match their own BOUN authors; the fetch cursor uses `from_publication_date` and caps at 200 works per run.
- **Open.** Decisions D1–D10 in the doc (model and dimension, runtime, aggregation, large collaborations, missing abstracts, self-matches, template, backfill, migrations, optional canaries).

### 2026-10-15 — Bibliographic coupling on the gold standard: references and pre-registration

- **Why.** Test whether coupling (a new paper and a researcher's paper cite the same works) predicts human-rated expertise, alone and on top of an embedding. Brief: `research/audit/BIBCOUPLING_PROMPT.md`.
- **Module.** `research/src/bibcoupling.py` (coupling variants, IDF, aggregations, forward/reverse citation, a port of the official weighted Kendall-tau loss with a seeded bootstrap, z-score and RRF fusion, leave-one-participant-out selection); 11 tests [632c0f1, 04c3f55]. The port reproduces every published baseline from the authors' prediction files (SPECTER2 max 0.221, o1-mini 0.245, TPMS 0.281, ...). The authors' `evaluation_script.py` is not run because it imports code from the downloaded data folder (user decision).
- **References from OpenAlex** (`research/scripts/fetch_goldstandard_openalex.py` [095add5]; cache `research/data/external/openalex_refs/`, gitignored). DOI and arXiv DOI (`10.48550/arxiv.<id>`) list calls; OpenAlex returns merged records whose main DOI can differ from the requested one, so results are matched through every DOI and arXiv id a record carries.
  - Coverage, papers with ≥1 reference: profile 696/867 (80.3%) vs Semantic Scholar 286/867 (33.0%); rated 401/463 (86.6%) vs 282/463 (60.9%). Above the 70% stop line, so OpenAlex is used. 115 papers unmapped (114 with neither id).
  - IDF: `cited_by_count` of the 29,579 distinct referenced works across all fetched records (592 list calls) and N = 101,086,105 OpenAlex works with references. 4,078 returned no count. Under the DOI-first rule 29,205 referenced works are in use, 4,037 of them without a count; those get the median weight.
  - Cost $0.0035 + $0.0593, anonymous (the Keychain key could not be read from the session; the anonymous budget is $0.10/day). The planned title search for the 114 (~$0.11) did not fit and was skipped.
- **Qwen3-Embedding check.** No HF reference weights locally, so the llama-server instance was checked against the verified v2 setup: 5 texts re-embedded match the cached v2 vectors (cosine 1.0000), and the server log shows `--pooling last` with no override warning.
- **Pre-registration** committed before any coupling score was computed [0020c68], at the top of `research/v2/14_bibcoupling_goldstandard.ipynb`: primary = IDF-weighted cosine coupling, max over profile papers; the other variants are one ablation table; fusion parameters by leave-one-participant-out; Holm families fixed; a same-record rule drops profile papers that share an OpenAlex record with the rated paper.
- **Results** (`research/v2/14_bibcoupling_goldstandard.ipynb`, outputs in `research/v2/goldstandard/`, figure `v2/figures/14_bibcoupling_goldstandard.*`) [8fe82c7]. Pooled loss, lower is better, 95% participant-bootstrap CI:
  - Coupling (primary) **0.299 [0.248, 0.348]**; constant 0.500. Embeddings (max): MiniLM 0.242 [0.194, 0.292], SPECTER2 [CLS] 0.231 [0.183, 0.282] (published 0.221; within the 0.02 sanity check), Qwen3-Embedding-8B 0.222 [0.177, 0.274].
  - Per-participant Wilcoxon, Holm over 10 tests: coupling beats constant (46 of 58 participants better, p_holm = 4.2e-06); coupling vs each embedding is not significant (p_holm ≥ 0.91; embeddings better for 32 participants).
  - Fusion (leave-one-participant-out): linear coupling + SPECTER2 **0.197 [0.148, 0.247]** vs SPECTER2 0.231, p_holm = 8.3e-03 (35 better, 9 worse); coupling + Qwen3 0.212 [0.164, 0.264] vs 0.222, p_holm = 1.0; coupling + MiniLM 0.233 vs 0.242, p_holm = 1.0. RRF fusion gains nothing.
  - Forward citation 0.468 [0.445, 0.488] (for 40 of 58 participants no rated paper cites a profile paper in any sample; 259 of 4,770 participant–paper–sample items are positive); reverse citation (selection artefact) 0.434 [0.403, 0.463].
  - Ablation (coupling kind × aggregation): 0.292–0.324. IDF from global counts is nearly flat (weights 10.6–16.1 between the 5th and 95th percentile), so IDF-cosine is close to plain cosine.
  - Pair-level stratification (descriptive): 70.2% of rated items share ≥1 reference with the profile. On pairs where both papers do, coupling 0.233 vs Qwen3 0.259; on the other pairs, coupling 0.362 vs Qwen3 0.187.
- **Examples caveat.** The pre-registered example rule cannot tell "coupling says no" from "no reference list": the first example (*Erasure Coding in Windows Azure Storage*) has no OpenAlex references, so its coupling score of 0 is missing data.
- **Not done.** Published baselines not yet checked against Table 3 of Stelmakh et al. (quoted from the authors' prediction files only); title search for the 114 papers without DOI or arXiv id (needs the API key); optional Experiment B (BOUN side).
- **Run time.** Qwen3 embedding of 1,311 texts took about 13 min, longer than the 5–10 min estimate.

### 2026-10-19 — Coupling follow-ups: Table 3, title search, coverage sensitivity

- **Commits rewritten.** The seven coupling commits were rewritten to drop their `Co-Authored-By` trailers (new global rule; not pushed, trees identical); hashes above updated [785d8f5].
- **Table 3 check.** All 11 published baselines recomputed from the authors' prediction files agree with Table 3 of arXiv 2303.16750v2 to the two decimals printed. The data card's "SPECTER2" (0.245) is "Specter2 Mean Pool" in the paper [93dec42].
- **Title search** for the 114 papers with neither DOI nor arXiv id ($0.114, anonymous, within the day's budget after all; the budget resets at 17:00 PDT). Year ±1 and a shared surname let through other papers by the same author (e.g. a POS-tagging paper for a spelling-normalization paper), so a title rule was added: normalized similarity ≥ 0.9, or the shorter title (≥ 3 words) contained in the longer. 5 first-pass hits failed it and were dropped; 67 of 114 matched, 54 with references [9e86e75]. Counts for the 434 + new referenced works went to a separate file so the pre-registered run stays reproducible [64aef41].
- **Pre-registered run reproduced.** Notebook 14 rebuilt with a `TITLE_SEARCH` option (addendum in its pre-registration cell) and rerun in the default mode: every CSV and prediction file is byte-identical [18f07b3].
- **Coverage sensitivity** (`v2/14_bibcoupling_goldstandard_titlesearch.ipynb`) [ad22667]. Profile coverage 80.3% → 85.2%, rated 86.6% → 89.0%. Coupling 0.299 → 0.292 [0.238, 0.343]; coupling + SPECTER2 0.199 (Holm p = 1.6e-02); coupling + Qwen3 0.219 vs 0.222 (Holm p = 1.0). No test conclusion changes.

### 2026-10-19 — BOUN-side coupling description (Experiment B, notebook 15)

- **Data** (`research/scripts/experiment_b_data.py` [143e37f]). The 200 most recent articles (15–19 Oct 2026) from the 7 followed institutions with an abstract and no BOUN author (2 list calls, $0.0002; `data/external/followed_sample/`, gitignored). Qwen3-Embedding-8B vectors for the 7,822 cleaned BOUN works and the sample (`data/v2/embeddings_boun/`, gitignored, reusable by the app seeder if the text template matches): about 1 h 45 min, slower than the 80 min estimate.
- **Brief correction.** The brief's "311 BOUN works with a followed co-author" came from the old `boun.csv`; the cleaned data has 642, of which 460 are 100+-author collaborations. The sanity check used the other 182 (152 with references, 110 with a BOUN author who has an earlier work).
- **Results** (descriptive, no labels) [2df0171]: 101 of 200 papers have references and 52 share ≥ 1 with a BOUN work (all 52 also a non-trivial one, cited by ≤ 1% of BOUN works). 22.9% of coupling's top researchers (≤ 10) are in Qwen3's top 10; coupling's top researcher sits at median rank 17 of 3,648 in the embedding ranking. Sanity check: own BOUN author in the top 10 for 80.0% of queries (embedding) and 72.7% (coupling); embedding-only 14, coupling-only 6, both 74, neither 16. Co-authors' shared self-citations favour coupling in this check.
- **Report.** README and `research/audit/SUMMARY.md` gained a gold-standard section (coupling, sensitivity, BOUN side) and an updated evaluation status.

### 2026-10-19 — Coupling as a label (notebook 16, post-hoc)

- **Why.** To back or refute a discussion point ("coupling cannot be a label") with numbers. Reuses notebook 14's pre-registered predictions; `bootstrap_ci` now accepts labels per profile sample [edcddde].
- **Results.** Strong coupling is precise: top decile of non-zero coupling, mean rating 4.50 [4.26, 4.69], 88% rated ≥ 4 (all items 3.71, 56%; same-size Qwen3 top 4.30, 82%). Top-1 by coupling vs Qwen3: 4.39 vs 4.37 (p = 0.59). With coupling scores as labels Qwen3 is still best (0.212); SPECTER2 and MiniLM swap; human ratings score 0.245.
- **Correction.** The earlier note's inference that a coupling-labelled benchmark would rank Qwen3 lower was wrong; PAPER_NOTES now says coupling is a high-precision silver positive with partial, biased coverage, not a full-ranking label.
