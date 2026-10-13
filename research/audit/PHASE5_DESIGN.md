# Phase 5 design: full-corpus retrieval and leakage-controlled graph expansion

Approved 2026-10-12. Tasks are in `TODO.md` (Phase 5); dated progress is in `docs/DEVLOG.md`.

## Why a separate citer pool

A co-citation graph can recover a positive only through a citer that cites both a seed and that positive. In the v2 cache, the only citers are the queries' references themselves. 43.6% of the 1,247 positive slots have at least one cached citer that is not a query paper and predates the owning query (median 0), and every one of those citers is itself a query's reference. A graph built from them sits on the answer key. Phase 5 therefore fetches a separate **citer pool**, selected without looking at any reference list.

## Data

| Step | What | Calls (estimate) |
|---|---|---|
| P0 | Probe on 4 dev queries (`scripts/probe_openalex_p0.py`) | 7, done |
| P1 | Refetch the 1,733 cached works with `doi` and `ids` into a new cache file; `openalex_works.jsonl` stays unchanged | 18 list calls |
| P2 | Citer pool: for each of the 168 queries, OpenAlex `search` on the query title, `to_publication_date` = the day before the query, `referenced_works_count:>9`, first 100 results | 168 search calls |
| P3 | Candidate corpus metadata: all eligible positives plus works cited by at least *m* pool citers, *m* chosen by corpus size only (target about 10k) | ~150 list calls |

**Selection uses only the query's own title**, never its references. OpenAlex topics are not used for selection. The topics docs say the classifier reads title, abstract and source name and "doesn't use citations"; references are not mentioned.

## Decisions (approved 2026-10-12)

1. **Citer pool:** per-query title search (option B). A label-blind field/year sample (option A) is only a robustness check, if budget allows.
2. **Corpus size:** about 10k first; 50k only if results warrant it. The 505,882-paper priority-institution corpus is not used: it holds 2020+ papers, the positives' median year is 2018, and citers must predate the query.
3. **Positives:** all eligible positives are in the corpus. The membership asymmetry this creates is measured with degree/popularity-only probes.
4. **Positives dated on/after the query** (21 of 1,247 in v2) stay exempt from the date filter, as in v2. A sensitivity run drops them.
5. **Citer exclusions:** all 168 query records and their near-duplicates.
6. **Duplicate query pair:** the dev copy `W3012006042` is dropped from Phase 5 dev; test stays at 118.
7. **Duplicate records** (DOI, normalized title, fuzzy match) are canonicalized in the corpus, the labels and the graph together.
8. **Rerank:** pointwise Llama over the full K = 100 list, one seed (greedy decoding, order-independent). Primary metrics are recall@100 and nDCG@10; R-precision and MRR are also reported.
9. **Tests:** pytest (new dependency), in `research/tests/`.
10. **Environment:** the worktree links `research/.venv` and `research/data/v2` to the main checkout.

## Changes during P2–P3 and notebook 08 (approved 2026-10-12)

- **Fallback search.** 72 queries whose title search returned fewer than 100 results got a second search on their first 6 content words.
- **Earlier versions count as duplicates.** Earlier versions of living reviews and guidelines are query duplicates under R3.
- **R3 matching**, settled by inspecting every match:
  - DOI, or exact normalized title (any year), or near-title.
  - Near-title means digit-free character similarity ≥ 0.9 **and** a shared author id.
- **Labels.** The 5 positives that are gone from OpenAlex or lack an abstract are dropped from the labels.
- **Checkpoint A decisions (2026-10-12).**
  - **R4 uses a conservative citer date.** A YYYY-01-01 date counts as YYYY-12-31, and a citer is never earlier than the latest known date among the works it cites. Recorded dates are reported as an upper bound, and a 365-day margin as a sensitivity check.
  - **A manual list of query duplicates** whose titles differ (NeRF ECCV ×2, the *"How do I fool you?"* preprint) was fixed before any method ran.
  - **Pool duplicates are merged** into one citer row, with united references and the latest member date.
- **Corpus size.** The corpus came out at 11,967 works, not 10k. The m = 5 threshold was fixed before the fetch, and eligibility (71.5%) beat the P0 estimate (63%).

## Leakage rules and controls

| Rule | Implementation | Control |
|---|---|---|
| R1 no query outgoing citations | the query is never a citer | canary: add the query's reference list as a citer |
| R2 query removed as citer | as R1, plus its duplicates (R3) | unit test |
| R3 duplicates | DOI + normalized title + fuzzy match; drop citers that duplicate any query | ablation: keep them |
| R4 temporal | each edge carries its citer's date; per-query filter `citer date < query date` | ablation: allow later citers; sensitivity with a 365-day margin |
| R5 no query citers | all 168 query records excluded | ablation: allow test queries |

- **Random-graph control:** degree-preserving rewiring of the citer-document bipartite graph (Curveball), 5 seeds.
- **kNN-graph control (LADR-style):** the same expansion over a document kNN graph from the embeddings, with no citations involved.

## Notebooks and modules

- **Notebooks** (in `v2/`):
  - `07_fetch_citers_corpus`
  - `08_build_corpus_graph`
  - `09_full_corpus_retrieval`
  - `10_graph_expansion`
  - `11_end_to_end`
- **Modules** (in `src/`):
  - `corpus.py`: citer and corpus fetch, canonicalization.
  - `cograph.py`: sparse incidence matrix with citer dates, per-query masks, co-citation scores, rewiring.
  - `retrieval.py`: exhaustive dense search, BM25 index, RRF, kNN graph.
  - `expansion.py`: GRIT- and LADR-style expansion, attribution.
- **Runs:** `v2/runs_corpus/`, kept apart from `v2/runs/`.

## Checkpoints

- **A:** P0–P3, citer coverage of positives, corpus statistics, duplicate counts. Before any embedding.
- **B:** stage-1 recall@k.
- **C:** graph, unit tests, canary and ablations, random graph.
- **D:** expansion parameters t and b on dev.
- **E:** end-to-end rerank and attribution on test.
