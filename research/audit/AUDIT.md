# v1 evaluation audit

Scope: the cited-paper ranking benchmark in `research/v1/03_cited_paper_ranking.ipynb`. Results are frozen in `research/v1/results/` (originally `research/eval_dataset/week3/`; git tag `v1-results`, commit `614cfb2`). Every number below is reproduced by:

```
python research/audit/verify_v1.py
```

## What could and could not be checked

The v1 intermediate caches are no longer available: `eval_sets.pkl`, `rankings.pkl`, `priority_followed.pkl` and `openalex_reference_works_raw.pkl`. `research/data/cleaned/boun.csv` is a different corpus; none of the 174 query papers or their 1,811 references are in it. So the audit uses two sources:

- **Code.** The notebook source, `src/`, and the cell outputs saved in `v1/03_cited_paper_ranking_out.ipynb` and `v1/01_fetch_and_preprocessing.ipynb`.
- **Saved rankings.** `rankings_*.json`, covering 100 queries. Each file stores only the **top-n_positives** candidate indices per query. In v1, candidate index `< n_positives` means positive.

Not checkable without the caches:
- per-query counts of positives vs negatives with a non-empty `concepts_array`
- per-query confirmation of F6
- stage-1 recall@k for k > n

## Summary

| # | Finding | Status | Affects |
|---|---|---|---|
| F1 | Candidates are passed in `positives + negatives` order | Confirmed (code) | Every LLM method |
| F2 | The prompt example `[3, 1, 7, ...]` points at a positive | Confirmed (data) | Every LLM method |
| F3 | A parse/HTTP failure returns the original order, so positives come first | Confirmed (data) | Llama, two-stage |
| F4 | Negatives have no `concepts_array`; the LLM sees title + concepts | Confirmed (code); counts not checkable | Every LLM method |
| F5 | "Stage-1 recall loss" does not explain the two-stage drop | Confirmed (data) | Two-stage claim |
| F6 | **Positive candidates were given the text of other papers** | Confirmed (code), consistent with data; per-query not checkable | **Every method** |
| F7 | `ndcg_at_n` is normalized by its own hits | Confirmed (code) | Every nDCG number |
| F8 | Negative sampling seed uses the per-process salted `hash()` | Confirmed (code) | Reproducibility |

**Net:** F6 means that, as far as the code shows, v1 measured rankings of mislabeled text for every method. F1–F4 then explain why the LLM still scored high: its signal came from candidate position and field presence, not from content. The v1 headline numbers should not be cited.

## Reference values

- The pool is n positives + 2n negatives. The JSON files don't store pool size, so 3n is assumed.
- Chance MRR is the exact expectation under a random ranking: **0.556**.
- Chance R-precision (the share of the top n that are positives) is **33.3%**.

| Method | MRR | R-prec % | top-1 = idx 0 | top-1 = idx 1 | top-1 = idx 2 | All-zero (fallback) | Negatives in top-n: mean relative position |
|---|---|---|---|---|---|---|---|
| Llama 3.2 3B (listwise) | 0.841 | 45.0 | 18 | 4 | **33** | **3** | **0.456** |
| Qwen3 → Llama | 0.589 | 37.0 | 1 | 1 | 3 | 3 | 0.497 |
| TF-IDF | 0.536 | 33.4 | 3 | 4 | 3 | 0 | 0.500 |
| MiniLM | 0.536 | 35.9 | 1 | 3 | 7 | 0 | 0.488 |
| Qwen3 + MiniLM | 0.526 | 37.2 | 2 | 2 | 5 | 0 | 0.483 |
| Llama + MiniLM | 0.522 | 34.5 | 1 | 1 | 8 | 0 | 0.495 |
| Qwen3 | 0.513 | 37.4 | 2 | 1 | 3 | 0 | 0.502 |
| EmbeddingGemma | 0.471 | 34.0 | 2 | 1 | 8 | 0 | 0.496 |
| SPECTER2 | 0.465 | 30.2 | 3 | 1 | 5 | 0 | 0.494 |
| BM25 | 0.410 | 23.1 | 1 | 1 | 2 | 0 | 0.492 |

The last column covers the negatives that a method placed in its top n. It gives where each sat within the original negative block: 0 = first negative, 1 = last. Random gives ≈ 0.5. Llama is the only method visibly skewed toward earlier negatives (0.456), which is consistent with position bias.

## F1 — Candidate order leak (confirmed, code)

Notebook cell 19:
```python
candidates = ev['positives'] + ev['negatives']
positive_indices = set(range(len(ev['positives'])))
```
Nothing shuffles the candidates. The LLM prompt numbers them `1..N` in this order, so the positives are always candidates `1..n`.

## F2 — Prompt example leak (confirmed, data)

`src/similarity.py:288` (and the Gemini copy at `:220`):
```
Respond ONLY with a JSON array of candidate numbers, e.g.: [3, 1, 7, ...]
```
Candidate number 3 is index 2. Because the minimum n is 3, index 2 is always a positive.
- Llama ranks index 2 first in **33/100** queries, and index 0 in 18/100.
- Other methods put index 2 first in 2–8/100 queries.
- The review's "~1–2%" figure for the other methods is too low; the measured range is 2–8%.

## F3 — Fallback leak (confirmed, data)

`src/similarity.py:312-318`: unranked candidates are appended in original order, and on any exception the function returns `[(i, 0.0) for i in range(n)]`.
- **Llama.** 3 queries hit the full fallback (W3081158114, W4220920296, W3037480398). All 3 return identity order and score MRR 1.0 by construction. Llama's MRR without them is 0.836, versus 0.841 with them. The fallback is a small part of Llama's lead.
- **Qwen3 → Llama.** 3 *different* queries fall back (W3018157127, W3128019209, W3014721972). There, the fallback returns the stage-1 order with zero scores.
- **Cause.** The saved notebook output shows repeated `403 Client Error: Forbidden` from `localhost:11434/api/chat` in a later run. The origin header likely needs fixing before any v2 run.

## F4 — Field asymmetry (confirmed from code; counts not checkable)

Cell 11 builds positives with `'concepts_array': row['concepts_array']`. The negatives dict has the keys `id, title, abstract, text, source` and **no `concepts_array`**.

Every LLM method builds its input as:
```python
' '.join(filter(None, [c.get('title', ''), ' '.join(c.get('concepts_array', []))]))
```
So in `llama`, `llama+minilm`, `qwen→llama` and `gemini`:
- **negatives were always title-only**
- **positives were title + concept tags** whenever their `concepts_array` was non-empty

A model can separate the two groups by format alone. Embedding and lexical methods use `c['text']` for both groups and are not affected by F4. The per-query counts the audit plan asked for need `eval_sets.pkl`, so they are **not checkable**.

## F5 — Two-stage drop is not stage-1 recall loss (confirmed, data)

Stage 1 keeps the top 20. For the 25 queries with n ≤ 6, the pool is 3n ≤ 20, so stage 1 drops **nothing**:

| Subset | Llama (full pool) | Qwen3 → Llama | Qwen3 |
|---|---|---|---|
| Pool ≤ 20 (25 queries) | 0.840 | **0.526** | 0.580 |
| Pool > 20 (75 queries) | 0.842 | 0.609 | 0.490 |

- **Small pools.** Recall loss is zero, yet the cascade scores *below Qwen3 alone* and 0.31 below full-pool Llama. The difference is the input order: stage 1 re-sorts candidates by Qwen3 score, which removes the positives-first order (F1/F2). The F4 asymmetry survives the cascade.
- **Stage-1 recall@k.** It can't be computed from the saved files, because they store only the top n.

## F6 — Positive candidates carry another paper's text (confirmed from code)

The chain in `v1/03_cited_paper_ranking.ipynb`, cells 6 and 12:
```python
extended_followed_df = pd.concat([followed_df, fetched_works_df])           # keeps original index labels
id_to_idx = {row['id']: i for i, row in extended_followed_df.iterrows()}   # id -> index *label*
...
row = extended_followed_df.iloc[id_to_idx[ref_id]]                          # used as a *position*
positives.append({'id': ref_id, 'title': row['title'], 'text': row['text'], 'concepts_array': ...})
```
Both frames were produced by `src/preprocessing.process_papers`. That function sorts by `publication_year`, filters rows, and never resets the index. The saved output in `v1/01_fetch_and_preprocessing.ipynb` confirms both frames went through it: the corpus went from 10,000 to 9,946 rows and the fetched references from 1,532 to 1,522.

Consequences:
- **Fetched references.** The fetched set (1,522 papers) has labels 0..1531. `iloc` on those labels returns rows of `followed_df`, i.e. **unrelated corpus papers**. The `id` stored on the positive is still the correct reference id, so nothing downstream would flag it. The corpus covers papers published since 2020 and references skew older, so most positives come from this fetched set.
- **In-corpus references.** These are misaligned too, by however far the sort and filter moved each row. One caveat: `process_papers` as committed (`df['language'] == 'en' or ...`) would raise on a Series, so the version that actually ran differs slightly from the repo.
- **Text field.** `build_text` was applied only to `followed_df`, so fetched rows never had a `text` field at all.

The saved scores are consistent with positives carrying no relevant content:
- **Chance level.** Every non-LLM method is at or below chance. MRR is 0.410–0.536 against a chance level of 0.556. R-precision is 23.1–37.4% against 33.3%.
- **Below chance.** BM25's R-precision of 23.1% (95% CI 20.8–25.4, `v1/stats/results.md`) is *below* chance with a CI that excludes it. An uninformative method can only do that if positives are systematically disadvantaged, for example through empty or short text.
- **The LLM.** Llama's 0.841 can then only come from F1–F4.

**Not checkable per query** without `eval_sets.pkl`. v2 must assert `positive['id'] == source_row['id']` on every candidate.

## F7 — nDCG normalization (confirmed, code)

`src/metrics.py:120-121`:
```python
top_n_hits = [...]
ideal_hits = sorted(top_n_hits, reverse=True)
```
The ideal DCG is built from the hits *the method retrieved*, not from `min(n, |positives|)` relevant items. A ranking with a single positive at rank 1 therefore scores nDCG 1.0. All v1 nDCG columns are mis-normalized.

## F8 — Non-reproducible negatives (confirmed, code)

Cell 11: `neg_pool.sample(..., random_state=hash(pi_id) % (2**31))`. Python salts `str.__hash__` per process (`PYTHONHASHSEED`), so the v1 negative pools cannot be regenerated even with the original corpus.

As a result, v2 rebuilds the pools for the same 174 queries. v1 → v2 is **not a paired re-run**.

## Out of scope

`backend/services/matching.py` has its own stage-2 LLM reranker. It does not import `ollama_rank_candidates` and was not audited. It uses `src.similarity` only for model maps.
