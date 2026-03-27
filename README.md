# SWE-599

This project aims to build an automated recommendation and matching system for academic publications. The system monitors a predefined list of publicators (institutions/publishers). When a new paper is released, it triggers a workflow to find and recommend similar articles and researchers specifically from the Boğaziçi University (BOUN) academic corpus.

### Core Workflow

- **Subscription & Trigger:** Users maintain a "Followed Publicators" list. The system monitors these sources for new releases.
- **Text Representation:** New publication metadata (titles/abstracts) are processed into high-dimensional vectors.
- **Similarity Search:** The system performs a similarity lookup against a local vector database of BOUN researchers and their past publications.

**Output:** A recommendation list linking global new releases to local (BOUN) expertise.


---

## Main Files

- `data/cleaned/boun.csv`
- `data/cleaned/priority_followed.csv`

---

## Week 1: Data Fetching & Benchmark Dataset

The immediate goal is to establish a benchmark dataset to evaluate different vectorization methods.

**Completed tasks:**

- **Data Collection:** Fetched 4,608 BOUN papers and 9,946 followed institution papers (post-2020) via the OpenAlex API.
- **Preprocessing:** Reconstructed abstracts from inverted index format; applied HTML cleaning, URL removal, stopword filtering, and keyword extraction. Cleaned data saved under `data/cleaned/`.
- **Benchmark Dataset:** Built 100 query-positive pairs using a 3-tier matching strategy — citation network (gold), topic/keyword overlap (silver), and concept fallback (bronze) (`eval_dataset/benchmark_pairs_with_related_works.json`).
- **Co-authoring Analysis:** Analyzed BOUN's top collaborating institutions (CNRS, Istanbul University, CERN, etc.) and research domains (particle physics, earthquake studies, etc.).
---

![swe599-1](https://github.com/user-attachments/assets/2920ef9f-2d3a-4889-95cb-e7c49ca2501e)
![swe599-2](https://github.com/user-attachments/assets/23c690d6-0736-4f35-a2e8-f82cf954e82e)

---

## Week 2: Dataset for Performance Evaluation & Embedding Comparison

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

--------

## Week 3: Detailed Cited Paper Ranking Dataset for Method Evaluation

Week 3 constructs a cited paper ranking dataset using papers from `data/cleaned/priority_followed.csv` (followed institutions) to test how embedding methods prioritize true references over random distractors from the followed corpus.

This extends Week 2's Task 3b with structured positives (citations) and hard negatives, enabling quantitative ranking metrics like precision@k. Reference lists are accessed via OpenAlex IDs or API fetches from the dataset metadata.

### Step 1: Select Main Papers (P_i)
Randomly sample 100 papers (P_i) from `priority_followed.csv` where each has 6-14 references (refCount ∈ ).
- Filter by `referenced_works_count` or equivalent field.
- Ensure references are resolvable in the corpus or fetchable via OpenAlex.

Output: `eval_dataset/week3/main_papers.json` with 100 P_i metadata.

### Step 2: Build Per-P_i Evaluation Set
For each P_i (refCount = n):
- Positives: n actual references (prioritize those in followed corpus; fetch abstracts/titles via OpenAlex otherwise).
- Negatives: 2n random papers from `priority_followed.csv`, excluding P_i's references and same-author works for hard negatives.

Result: Per P_i set of 3n candidates (n positives + 2n negatives); P_i as query.

### Step 3: Compute Embeddings and Rankings
Embed P_i (title/abstract/concepts) and 3n candidates using Week 2 methods: TF-IDF + Cosine, Sentence Transformers, Gemini API, Google Embedding Model.
- Rank all 3n candidates by similarity score to P_i.
- In top-n results: Count how many (a) are true references out of n slots; compute hit rate = (a / n) × 100%.

Save: `eval_dataset/week3/rankings_{method}.json` with full ranks, scores, and per-query hit rates.

### Step 4: Evaluation Metrics and Comparison
Aggregate across 100 queries; report per-method: Mean, Std Dev, Median.
- Hit Rate %: Average percentage of top-n filled by true references.
- Precision@n: Equivalent to mean hit rate.
- MRR: Mean reciprocal rank of first positive.
- nDCG@n: Ranking quality accounting for all positives' positions.

| Metric | TF-IDF + Cosine | all-MiniLM | SPECTER2 | Gemini (LLM as judge) | Google Embed |
|--------|-----------------|------------|----------|--------|--------------|
| Mean Hit Rate % | - | - | - | - | - |
| Std Dev Hit Rate % | - | - | - | - | - |
| Median Hit Rate % | - | - | - | - | - |
| Mean MRR | - | - | - | - | - |
| Mean nDCG@n | - | - | - | - | - |

These metrics identify methods best at surfacing citations from followed institutions.

--------

### Gemini Ranking Approach

Instead of scoring each candidate individually (one API call per paper), Gemini ranks all candidates in a **single prompt**. For each query, the prompt contains:

- **Main Paper** (title + abstract, up to 800 chars)
- **Candidate Papers 1–N** (18–42 papers, up to 600 chars each)

Gemini returns a JSON array of candidate numbers ordered by relevance, e.g. `[7, 2, 15, ...]`. Scores are derived from rank position: rank-1 → `1.0`, rank-N → `~0.0`.

**Why this approach:**
- 1 API call instead of 18–42 calls per query → ~40× fewer requests
- Gemini compares candidates *relative to each other*, not in isolation
- Fits comfortably within Gemini 2.5 Flash's 1M-token context window

**Implementation:** `gemini_rank_candidates(query_text, candidates)` in `src/similarity.py`.

--------

