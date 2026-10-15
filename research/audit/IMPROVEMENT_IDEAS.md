# SWE-599 v2: Improvement Ideas

Ideas collected while reading papers from target PhD labs and auditing the v1 code.
Status: ideas only. Nothing here is a result yet. Every number marked "v1" comes from the
current repo; every number marked "TBD" must come from new experiments.
*(Original framing. Results were added later in the dated status notes.)*

> **Status (2026-10-14).**
> - Idea A and the fixed-pool part of Idea D were done on branch `v2-audit` (2026-10-12; see `BEFORE_AFTER.md`).
> - Ideas C and D were done in full in Phase 5 (notebooks 07–12, branch `v2-phase5`; see `PHASE5_DESIGN.md`).
> - Status notes below are added in quote blocks; the original text is unchanged.

---

## 0. Why v2 is needed: audit of v1

The v1 headline (Llama 3.2 3B listwise reranker MRR 0.84 vs Qwen3 0.51) is likely inflated.
Evidence from the code and `research/eval_dataset/week3/`:

| Issue | Where | Evidence |
|---|---|---|
| Positives always listed first, never shuffled | `cited_paper_ranking.ipynb` (candidates = positives + negatives) | positive_indices = range(n) |
| Prompt example `[3, 1, 7, ...]` acts as an answer hint | `src/similarity.py`, `ollama_rank_candidates` | Candidate 3 (always a positive) ranked first in 33/100 queries; ~1–2% for embedding methods |
| Parse-failure fallback returns original order (positives first) | same function | 3 queries got a "free" perfect ranking; unranked items also appended in original order |
| Possible field asymmetry | negatives built without `concepts_array`; LLM input = title + concepts | Not yet verified (needs `eval_sets.pkl`) |
| "Stage-1 recall loss" explanation is weak | two-stage keeps top-20 | 25/100 queries have pools of 20 or fewer candidates, so nothing can be lost there; the cascade also removes the positives-first ordering |

On the 64 queries that are not "candidate 3 first" or fallback, Llama MRR is 0.75 vs Qwen3 0.55,
but those queries still have positives-first ordering. The true gap is unknown until a clean rerun.

> **Verified (`AUDIT.md`, `verify_v1.py`).** All five issues are confirmed. Corrections and additions:
> - **Other methods.** They put candidate 3 first in 2–8 of 100 queries, not ~1–2%.
> - **Field asymmetry** is confirmed from code: the negatives dict has no `concepts_array` key. The per-query counts cannot be computed because `eval_sets.pkl` is gone.
> - **The 64-query numbers** reproduce: Llama MRR 0.752 vs Qwen3 0.551.
> - **Bigger problem (F6).** Positives carried *other papers' text*: a DataFrame label was used as a row position. Every non-LLM v1 method sat at or below chance (chance MRR 0.556).
> - **F7, F8, F9.** nDCG was mis-normalized (F7). Seeds came from Python's salted `hash()` (F8). SPECTER2 was run with mean instead of [CLS] pooling (F9).
> - **The true gap is now known.** On the clean v2 protocol, the gap reverses (section 7).

**Framing for applications:** "I audited my own LLM-reranking benchmark, found the LLM's apparent
advantage was partly driven by candidate-order and prompt artifacts, and rebuilt the evaluation."
This fits trust / verification of AI output directly.

> The evidence now supports a stronger version: the advantage was **entirely** an artifact. On the clean protocol, listwise Llama is the weakest of 13 methods. Candidate order alone moves its MRR from 0.95–0.98 (positives first) to 0.27–0.33 (positives last).

---

## 1. Idea A: Clean evaluation protocol

- Shuffle candidates per query with a logged seed; run several seeds and report the spread.
- Neutral prompt format with no example indices.
- Count and report parse failures; fall back to a random order, not the original order.
- Identical input fields for positives and negatives, for every method.
- Time filter: candidates must be published before the query paper.
- Dev/test split; tune only on dev (the v1 field ablation used the same 100 queries it reported on).
- Evaluate all 174 queries.
- Fair comparisons: add a pointwise LLM variant and a cross-encoder baseline.
- Contamination check: split queries by publication date relative to the LLM's knowledge cutoff.

> **Done**, with two deviations:
> - **Query count.** 168 of 174 queries are usable; 50 are dev and 118 are test.
> - **Contamination.** It could not be tested: only one test query is after Llama 3.2's December 2023 cutoff.
>
> Seed spread over 5 shuffles is 0.8–2.0 R-precision points. Full-list Llama returns a partial ranking in 38% of calls.

---

## 2. Idea B: A better benchmark (from CC30k and citation-intent work)

### The problem: citation is not the same as relevance

v1 treats every cited paper as equally relevant. Citations serve different functions
(background, method use, comparison, critique, perfunctory "standard" citations).
CC30k (Obadage, Rajtmajer, Wu, JCDL 2025) shows how much citations vary in what they say about
the cited work: in its crowdsourced portion, about two thirds of citation contexts were neutral
(they mention the paper without any reproducibility signal). Related datasets classify citation
intent (SciCite, ACL-ARC) and influential vs incidental citations (3C shared task).

### Design for benchmark v2

1. **Graded relevance instead of binary.**
   - Level 3: influential / method-use citations (e.g. cited several times, used or extended).
   - Level 2: topical background citations.
   - Level 1: perfunctory citations (cited once, in a long list, generic background).
   - Level 0: not cited.
   - Possible signals: Semantic Scholar citation intents, influential-citation flag, citation
     contexts, mention count. (Verify current S2 API fields before relying on them.)
   - Report nDCG with graded labels next to binary MRR, and check whether method rankings change.
2. **Hard negatives.** Topically close, uncited papers, published before the query, from the same
   field. Random negatives make the task too easy.
3. **False negatives (relevant but uncited).** Pool the top results from all methods
   (TREC-style pooling) and get judgments on a subset.
4. **Human validation subset.** 20–30 queries judged by researchers (the deployed system's
   thumbs-up/down data can help). Measure agreement between the citation proxy and human judgments.
   This agreement number is a finding in itself.
   *(Dropped 2026-10-15: the project will have no human evaluation.)*
5. **LLM-as-judge only if validated.** If an LLM is used to label at scale, report its agreement
   with the human subset first. (Same concern as GRIT's TQE benchmark, where the same model
   generated and validated the queries.)
6. **Data quality flags.** Some OpenAlex "abstracts" are not abstracts (e.g. the ADMET-AI query
   paper's abstract is a software availability statement). Detect and flag/filter these.
   Connects to Jian Wu's work on scholarly big data quality.

> **Status.**
> - **Item 2 is partial.** The `concept` benchmark requires a shared top-5 OpenAlex concept, which often matches only a broad field such as "Medicine". It is harder than random negatives (every method scores lower, by 2–10 R-precision points; about 7 for the embedding models), but these are not same-topic hard negatives.
> - **Item 6 is done.** See `DATA_QUALITY.md`.
>   - About 6% of papers carry text that is very likely not their abstract: author lists, citation strings, journal standfirsts, fragments, and in two queries another paper's title.
>   - One paper appears as two query records.
>   - In v2 the ADMET-AI abstract is a real abstract, because v2 reconstructs it directly from OpenAlex.
>   - Results are robust: dropping the flagged test queries moves no method by more than about 1 point.
> - **Items 1, 3, 4 and 5 are open** (Phase 4).

---

## 3. Idea C: Leakage control for citation-graph expansion

Using a citation graph to find candidates is powerful because citations are also the labels.
That is exactly why leakage control has to be explicit.

### Leakage types and rules

| Type | What goes wrong | Rule |
|---|---|---|
| Direct | The query's own reference list is in the graph, so the system reads the answer key | Never include the query paper's outgoing citations |
| Via the query as citer | Co-citation edges computed from citing papers include the query paper itself | Remove the query paper from the set of citers |
| Duplicates | Preprint and published versions, or near-duplicate records of the query, carry the same reference list | Deduplicate by DOI and title similarity; drop near-duplicates of test queries from the citer set |
| Temporal | Edges built from papers published after the query = future information | Build the graph only from citing papers published before the query (or use a global time cutoff: graph before T, test queries after T) |
| Test–test | Other test queries' reference lists enter the graph | Build the graph only from non-test citing papers (GRIT's train/test logic) |

> **Note from the data.** The duplicate rule matters in practice. One query paper exists as two OpenAlex records, and 17 of 1,247 positives are duplicate records of a paper already among the positives (`DATA_QUALITY.md`, `docs/DEVLOG.md`).

### Built-in sanity checks

- **Leakage canary:** deliberately include the query's own references. Scores should become near
  perfect. If they don't, the pipeline is broken. Then remove them and report the drop.
- **Random-graph control:** a graph with the same degree distribution but random edges.
  Gains should vanish; if they don't, the gain isn't coming from citation structure.
- **Attribution:** report what fraction of recovered positives came through the graph.

> **Status (2026-10-14): done in Phase 5** (notebooks 08 and 10; test split).
> - **Rules R1–R5** are each implemented as a row mask and unit-tested (`research/tests/test_cograph.py`). R4 uses a conservative citer date, because 24% of citers carry year-only Jan 1 dates.
> - **Leaks the rules caught:**
>   - a 2012 record of a Cochrane review holding all 10 of a 2020 query's references;
>   - an earlier, differently titled version of a query (NeRF), excluded by a manual list.
> - **Reachability** (positives cited by at least one allowed citer): 54.7% under all rules, 62.9% with recorded dates, 70.1% with R3–R5 off.
> - **Canary:** +5.8 recall@100 [+3.6, +8.2], against +0.8 [−0.4, +2.1] under all rules.
> - **Random graphs** (Curveball, 5 seeds): −0.5 to −0.9.
> - **Attribution:** 20 of 548 positives (3.6%) in the expanded top 100 came through the graph.

---

## 4. Idea D: First-stage recall study (from LADR and GRIT)

- Move from fixed small pools to full-corpus retrieval (~10k papers).
- Measure Qwen3 / BM25 / hybrid recall at k = 5, 10, 20, 50, 100.
- LADR-style: lexical seeds, then expand through a document kNN graph.
- GRIT-style: seeds from the top results, then replace the bottom part of the list with
  co-citation neighbors (leakage-controlled, Idea C). Keeps the list length constant.
- Then rerun the LLM reranker on the improved candidate list and measure end-to-end gains.

> **Status: on fixed pools only** (at most 42 candidates per query; test split; `random` / `concept`).
>
> | Recall | Qwen3 | BM25 | BM25 + Qwen3 (RRF) |
> |---|---|---|---|
> | @10 | 92.5% / 89.0% | 80.8% / 76.2% | 89.0% / 84.2% |
> | @20 | 99.0% / 97.9% | 96.1% / 94.7% | 98.7% / 97.5% |
>
> - **The hybrid does not beat Qwen3 alone.**
> - **Reranking still hurts.** Llama reranking of Qwen3's top 10 still lands 10–13 R-precision points *below* Qwen3, so on these pools the reranker, not stage-1 recall, is the bottleneck.
>
> **Status (2026-10-14): full corpus done in Phase 5** (11,967 papers; test split, 118 queries; notebooks 09–12).
> - **Recall@100:** Qwen3 64.0% [58.7, 69.4], BM25 38.7%, BM25 + Qwen3 (RRF) 60.2%. The hybrid again does not beat Qwen3.
> - **GRIT-style expansion** (t = 5, b = 10%, chosen on dev): +0.8 recall@100 [−0.4, +2.1], not significant.
> - **LADR-style**, BM25 seeds plus a kNN graph: 62.3% recall@100, scoring 12.5% of the candidates.
> - **End to end:**
>   - pointwise Llama 3.2 3B lowers nDCG@10 from 0.340 to 0.175 (alone) or leaves it unchanged (fused);
>   - Qwen3-Reranker-4B, fused, raises R-precision from 25.1% to 28.3% (Holm p = 0.040) and nDCG@10 to 0.360 (not significant after Holm).

---

## 5. Idea E: Human-centered trust study (for HCI labs)

The deployed system already logs thumbs-up/down feedback.

- Does offline ranking quality predict what researchers find useful?
- Do researchers trust LLM-produced recommendations differently from similarity scores?
- Does showing an LLM explanation change acceptance, and does it help or hurt calibration?

---

## 5b. Idea F: Researcher-level evaluation on BOUN data (added 2026-10-12)

**Why.** The benchmark (v1 `03` and all of v2) measures paper → cited papers. Every query and every candidate comes from the followed institutions' papers and their references. The deployed app does a different task: it recommends a new paper to a *researcher*.

**How the app uses BOUN data** (`backend/services/seeder.py`):
- BOUN-affiliated authors (`I4405392`) are extracted from `research/data/cleaned/boun.csv` (4,608 papers, 2020+, English). This gives 2,671 researchers and 7,803 researcher–paper rows, the "~7,800 BOUN paper embeddings" in the README.
- Stage 1 matches a new paper against those embeddings and groups the scores by researcher.
- Stage 2 gives Llama the new paper plus the researcher's 5 most similar BOUN papers (`RAG_CONTEXT_PAPERS`) and scores each researcher **pointwise**.

v2's results are therefore strong evidence about the app, but not a direct test of it. `APP_NOTES.md` already notes that the deployed stage 2 is untested.

Elsewhere, BOUN data appears only in v1 exploratory checks:
- the Week 1 pairs benchmark (`v1/pairs_benchmark/`), with semi-automatic labels;
- the qualitative similarity checks in `v1/02_similarity_evaluation.ipynb`;
- an archived co-authoring notebook.

**`boun.csv` was never audited.** The F6 label/position bug likely does not apply, because the backend reads the file row by row. Two checks already show that the v2 data-quality issues are likely present:
- **1,605 of the 4,608 rows have no abstract.** The app embeds those papers from title and concepts only.
- Non-abstract "abstracts" (about 6% in v2) and duplicate OpenAlex records are still to be checked.

> **Update (2026-10-15).** Audited by a full refetch; see `BOUN_DATA.md`. `boun.csv` also holds non-research types (errata, editorials), lacks conference papers, preprints and book chapters, and cuts author lists at 100 (223 records). The cleaned data in `research/data/boun/` has 7,822 works with text for 84.2%.
>
> **Task restated (2026-10-15).** The app lists, under each new followed-institution paper, the BOUN researchers who work on its topic. Relevance is topical expertise. The citation-based task below ("papers a researcher later cites") does not match it and is paused; see `docs/DEVLOG.md`.

**Task.** For a BOUN researcher, are the external (followed-institution) papers that they later actually cite ranked near the top when recommended to them? This is the app's real task, and citations label it automatically.

**Design sketch.**
- **Profile:** the researcher's BOUN papers published before a cutoff T.
- **Candidates:** followed-institution papers published before T.
- **Positives:** candidates cited by the researcher's BOUN papers published after T.
- The time split is a natural leakage control.

**Compare.**
- Profile aggregation: max vs mean over the researcher's paper embeddings.
- The v2 stage-1 methods.
- The deployed pointwise Llama stage 2 on top of stage 1, against stage 1 alone.

**Leakage rules** (same spirit as Idea C):
- no post-T information in profiles or candidates;
- deduplicated records (preprint/published, duplicate OpenAlex ids);
- positives come only from post-T citing papers.

**Open questions.**
- The cutoff T.
- Minimum number of pre-T papers and post-T positives per researcher.
- Which followed-institution corpus to use for candidates. v1 had only the first 10,000 of 505,882 papers, so a fetch is likely needed.
- How to handle multi-author papers that link several researchers.

**Labs.** Mainly Goharian (IR evaluation of a deployed two-stage system) and Yan Chen (it connects to the trust study through the app's thumbs-up/down data, Idea E).

---

## 6. Which idea fits which lab

| Lab | Most relevant ideas |
|---|---|
| Goharian, Georgetown IR Lab (LADR, GRIT) | C, D, F, plus A |
| Jian Wu, ODU LAMP-SYS (CC30k, data quality) | B, data-quality flags |
| Yan Chen, Virginia Tech PRIME (trust, delegation) | E, F, plus the audit story in section 0 |

---

## 7. Draft pitch sentences (fill in TBD after experiments)

- "I audited my LLM-reranking benchmark and found that candidate order and a prompt example
  inflated the LLM's advantage; with a controlled protocol the gap is TBD."
- "Stage-1 recall at k=20 is TBD; a leakage-controlled co-citation expansion recovers TBD of the
  missed references and lifts end-to-end MRR from TBD to TBD."
- "Citation-proxy labels agree with researcher judgments on TBD of pairs, which motivates graded,
  context-aware relevance labels."

> **Filled where v2 has the numbers** (2026-10-12, test split, 118 queries):
>
> - "I audited my LLM-reranking benchmark and found that its headline result, a 3B LLM reranker beating embedding retrieval (MRR 0.84 vs 0.51), was an evaluation artifact. Candidates were always shown positives-first, and positive candidates even carried the wrong papers' text. With a controlled protocol (shuffled candidates, identical inputs, dev/test split, 5 seeds), the LLM ranks last of 13 methods: 44% R-precision vs 87% for Qwen3 embeddings. Changing only the candidate order moves its MRR from 0.95 to 0.33."
> - "On fixed candidate pools, stage-1 recall at k=20 is 99% (Qwen3), and LLM reranking of the top 10 *lowers* R-precision by 13 points. Over a full 12k-paper corpus, recall@20 drops to 41% and recall@100 to 64%. A leakage-controlled co-citation expansion recovers only 6% of the missed references (+0.8 recall@100, not significant), while its canary shows +5.8 when the answer key leaks in. End to end, a small general LLM halves nDCG@10, and only a trained reranker (Qwen3-Reranker-4B, fused) helps: R-precision 25% → 28%." *(Filled 2026-10-14 from notebooks 09–12. The original sentence assumed the expansion would lift end-to-end MRR; it does not.)*
> - "Citation-proxy labels agree with researcher judgments on TBD of pairs, which motivates graded, context-aware relevance labels." *(Needs Phase 4.5, which was dropped on 2026-10-15; this sentence will not be filled.)*
