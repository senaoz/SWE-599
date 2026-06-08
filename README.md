# NLP-based Scientific Article Suggestion System

**SWE 599 — Term Project**  
Sena Öz · Advisor: H. Birkan Yılmaz  
Boğaziçi University, 2026

[`Final Report PDF`](SWE599_Final_2026S_OZ_Sena.pdf)

<img width="6600" height="4665" alt="599poster" src="https://github.com/user-attachments/assets/fe233979-4516-4200-8e78-d8435749bd96" />

---

## Overview

This repository contains the full implementation and research code for an NLP-based academic paper recommendation system targeting Boğaziçi University (BOUN) researchers. The system monitors a configurable set of academic institutions via the [OpenAlex API](https://openalex.org), detects newly published papers, and matches them against BOUN researcher profiles using a two-stage Retrieval-Augmented Generation (RAG) pipeline.

<img width="914" height="1124" alt="System overview" src="https://github.com/user-attachments/assets/94ce3246-9413-4d54-9f56-d9dd9627e3f6" />

---

## Research Summary

### Problem

The volume of academic publications is growing at an unprecedented rate. Researchers face an increasing challenge staying up to date with newly published work from peer institutions. Existing platforms such as Semantic Scholar provide general-purpose suggestions but are not tailored to an institution's specific researcher profiles.

### Approach

A two-stage RAG pipeline:

- **Stage 1 — Retrieve:** Qwen3 dense embeddings + cosine similarity via `pgvector` to narrow the candidate set from the full BOUN researcher corpus.
- **Stage 2 — Rerank:** Llama 3.2 3B via Ollama reasons over the top-10 candidates using a structured natural-language prompt.

### Embedding Method Evaluation

Nine methods were benchmarked on a cited paper ranking task (174 query papers, 100 sampled for evaluation). Each query paper's true references served as positives; 2× random papers as negatives.

| Method | Hit Rate % | MRR | nDCG@n | Top-1 |
|---|---|---|---|---|
| **Llama reranker** | **44.99** | **0.841** | **0.838** | **75%** |
| Qwen | 37.42 | 0.513 | 0.642 | 25% |
| Qwen+MiniLM | 37.22 | 0.526 | 0.640 | 30% |
| MiniLM | 35.90 | 0.536 | 0.632 | 33% |
| Llama+MiniLM | 34.50 | 0.522 | 0.633 | 30% |
| embeddinggemma | 33.95 | 0.471 | 0.603 | 25% |
| TF-IDF | 33.41 | 0.536 | 0.629 | 32% |
| SPECTER2 | 30.21 | 0.465 | 0.582 | 24% |
| BM25 | 23.09 | 0.410 | 0.528 | 18% |

The Llama 3.2 3B reranker substantially outperforms all dense embedding methods — 7 pp above Qwen in hit rate and 50 pp in Top-1 accuracy — motivating the two-stage production design.

---

## Dataset

- **BOUN Corpus:** 4,608 English-language papers with non-empty abstracts, fetched from OpenAlex for BOUN-affiliated authors.
- **Followed Institutions Corpus:** 9,946 post-2020 papers from MIT, Stanford, Harvard, UC Berkeley, University of Michigan, Google, and Google DeepMind.
- **Benchmark:** 174 query papers, each with 6–14 cited references as positives and 2× random negatives, constructed in [`research/cited_paper_ranking.ipynb`](research/cited_paper_ranking.ipynb).

Text representation: title + abstract + OpenAlex concept tags (ablation showed this combination consistently outperforms title-only or abstract-only).

---

## Repository Structure

```
├── backend/                  # FastAPI + PostgreSQL + pgvector service
├── frontend/                 # React 19 + TypeScript SPA
├── research/
│   ├── src/
│   │   ├── similarity.py     # All 9 embedding/ranking implementations
│   │   ├── preprocessing.py  # Abstract reconstruction + text cleaning
│   │   └── metrics.py        # Hit rate, MRR, nDCG
│   ├── fetch_and_preprocessing.ipynb
│   ├── similarity_evaluation.ipynb
│   └── cited_paper_ranking.ipynb
├── docs/
│   ├── final_report.tex      # Full project report
│   └── references.bib
└── docker-compose.yml
```

---

## Research Progress

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

Built a production-ready recommendation system on top of the Week 1–3 research pipeline. See [README_APP.md](README_APP.md) for setup and run instructions.

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

## Running the Application

For setup, deployment, and configuration instructions, see **[README_APP.md](README_APP.md)**.
