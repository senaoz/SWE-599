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

## Week 2: Performance Evaluation & Embedding Comparison

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
| **Sentence Embeddings** | e.g. `all-MiniLM`, `SPECTER2` |
| **Gemini API** | Prompt Gemini to score semantic similarity between two papers directly |

Produce a comparison table: for each method, report top-3 retrieved papers per query along with similarity scores. Evaluate against the benchmark pairs from Week 1 where applicable.

---

### Task 3 — Intra-Paper Similarity (Sanity Checks & Ground Truth Validation)

These tasks validate that the similarity pipeline ranks known-relevant papers highly, serving as a qualitative sanity check.

**3a. Same-Author Paper Ranking**

- Given a target paper, retrieve all other papers by the same author(s) from the BOUN corpus.
- Rank them by similarity score to the target paper.
- Expected: thematically related works by the same author should rank near the top.

**3b. Cited Paper Ranking**

- Given a target paper, retrieve its reference list (papers it cites) from the dataset.
- Rank the cited papers by similarity score to the target paper.
- Expected: directly cited works should score higher than unrelated papers, validating the embedding quality.
