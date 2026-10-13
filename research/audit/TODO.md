# SWE-599 v2: TODO Plan

How to use with Claude Code: put this file and `IMPROVEMENT_IDEAS.md` in `research/audit/`. Ask Claude Code to execute one task at a time, tick the checkbox when its acceptance criteria are met, commit, and stop at every CHECKPOINT to report to me.

Global rules:

* Never modify `research/eval_dataset/week3/` (v1 results). New outputs go to `research/eval_dataset/v2/`.
* Never invent numbers. If something can't be computed, say so in the report.
* Estimate runtime and ask before any long Ollama / API run.
* Fix random seeds and log them for every run.

Suggested timing: Phase 0–1 before the Georgetown visit (~Oct 18). Phases 2–5 before December deadlines.

> **Status (2026-10-12).** Ticks below reflect work on branch `v2-audit` (PR senaoz/SWE-599#1); dated details are in `docs/DEVLOG.md`.
> - **Paths differ from this plan.** The research folder was reorganized. v1 results moved unchanged from `research/eval_dataset/week3/` to `research/v1/results/`, byte-identical to tag `v1-results`. v2 outputs live in `research/v2/` (notebooks `01`–`06`, `eval_sets/`, `runs/`, `stats/`, `figures/`).
> - **Model server.** Ollama was replaced by local llama-server (GGUF) and sentence-transformers.

## Phase 0: Protect the baseline

* [x] 0.1 Create tag `v1-results` and branch `v2-audit`.
   * Done when: tag and branch exist; `git status` clean.
   * *Done: tag `v1-results` on 614cfb2, pushed to GitHub; branch pushed.*
* [x] 0.2 Create `research/audit/` and `research/eval_dataset/v2/`; copy in this plan and the ideas file.
   * *Done: `research/audit/` holds this plan and the ideas file; v2 outputs are in `research/v2/` (see status note).*

## Phase 1: Verify the audit findings (no fixes yet)

* [x] 1.1 `research/audit/verify_v1.py`: position stats per method (how often each candidate index is ranked first; how often candidate 3 is first).
* [x] 1.2 Count parse-failure fallbacks (all-zero scores) per LLM method.
* [x] 1.3 Field asymmetry: load `eval_sets.pkl`, count non-empty `concepts_array` for positives vs negatives per query.
   * *`eval_sets.pkl` no longer exists, so the per-query counts cannot be computed. The asymmetry is confirmed from code: the negatives dict has no `concepts_array` key (AUDIT.md F4).*
* [x] 1.4 Count queries whose pool size is 20 or fewer (no possible stage-1 loss at top-20).
* [x] 1.5 Data quality: flag abstracts that look like non-abstracts (availability statements, very short text, URLs/DOIs only).
   * *Done on the v2 data: `research/audit/DATA_QUALITY.md`, `research/audit/data_quality.py`.*
* [x] 1.6 Write `research/audit/AUDIT.md` with all numbers and what could not be checked.
* CHECKPOINT 1: stop and show AUDIT.md. *(Shown 2026-10-09. The audit also found F6 (positives carried other papers' text), F7 (nDCG normalization), F8 (salted seeds) and later F9 (SPECTER2 pooling).)*

## Phase 2: Clean evaluation protocol

* [x] 2.1 Shuffle candidates per query with a logged seed; save permutations.
* [x] 2.2 Neutral LLM prompt with no example indices.
* [x] 2.3 Parse failures: log, count, random-order fallback; report failure rate.
* [x] 2.4 Identical input fields for positives and negatives in every method.
* [x] 2.5 Add publication dates (OpenAlex); keep only candidates published before the query.
   * *Applied to negatives. Positives are the query's own references; 21 of 1,247 carry an OpenAlex date on or after the query, because OpenAlex dates are sometimes wrong.*
* [x] 2.6 Seeded dev/test split; move all tuning (fields, top-k) to dev.
* [x] 2.7 Run all 174 queries; LLM with 3–5 shuffle seeds (estimate runtime first).
   * *Deviation: 168 of 174 queries are usable (5 lack an abstract or date, 1 has only 2 usable references). 50 form the dev split, so test results cover 118 queries. LLM methods ran with 5 seeds.*
* [x] 2.8 Rerun significance pipeline (bootstrap CIs, Holm-corrected Wilcoxon) on v2.
* CHECKPOINT 2: v1 vs v2 table for every method. *(`research/audit/BEFORE_AFTER.md`)*

## Phase 3: Diagnostic analyses

* [x] 3.1 Position-bias experiment: original vs shuffled vs reversed order, same queries.
* [x] 3.2 Stage-1 recall at k = 5, 10, 20, 50 for Qwen3, BM25, and a hybrid.
   * *Pools hold at most 42 candidates, so k = 50 is trivially 100%. Fixed pools cap this diagnostic; full-corpus recall is Phase 5.*
* [x] 3.3 Contamination: split queries by date around the LLM's knowledge cutoff (verify cutoff from the model card).
   * *Cutoff December 2023 (Meta model card). Only 1 test query is later, so the comparison cannot be interpreted.*
* [x] 3.4 Pointwise LLM variant.
* [x] 3.5 Cross-encoder baseline (e.g. a bge-reranker model).
* CHECKPOINT 3: short findings note. *(Findings cells in `v2/05_stats.ipynb` and `v2/06_analysis.ipynb`; `docs/DEVLOG.md`)*

## Phase 4: Benchmark v2 (better labels and negatives)

* [ ] 4.1 Hard negatives: topically close, uncited, published before the query, same field.
   * *Partial: the `concept` benchmark requires a shared top-5 OpenAlex concept. This often matches only a broad field label (e.g. "Medicine"), so these are not same-topic hard negatives.*
* [ ] 4.2 Graded labels: fetch citation contexts / intents / influential flags (verify available Semantic Scholar API fields first); define levels 0–3 as in IMPROVEMENT_IDEAS.md.
* [ ] 4.3 Report graded nDCG next to binary MRR; check whether method rankings change.
* [ ] 4.4 Pooling: collect top-10 from all methods per query for a judgment subset.
* [ ] 4.5 Human judgment protocol for 20–30 queries (instructions + simple form); measure agreement with citation labels.
* [ ] 4.6 Optional: LLM judge, only reported with its agreement against the human subset.
* CHECKPOINT 4: benchmark v2 card (size, label distribution, agreement numbers).

## Phase 5: Full-corpus retrieval + leakage-controlled graph expansion

> **Status (2026-10-12).** Design approved: `PHASE5_DESIGN.md` (branch `v2-phase5`). P0 probe done (`scripts/probe_openalex_p0.py`, 7 calls on 4 dev queries). P1–P3 done (`v2/07_fetch_citers_corpus.ipynb`): 10,663 citers, corpus of 9,706 works (1,176 positives), 62% of positive slots reachable through an allowed citer. Notebook 08 done: 11,967-work corpus, labels for 48 dev / 118 test queries, graph with rules R1–R5, 11 unit tests pass. Next: CHECKPOINT A review, then notebook 09 (embeddings).

* [ ] 5.1 Full-corpus first stage over ~10k papers; recall at k up to 100.
* [x] 5.2 Co-citation graph builder with leakage rules: no query outgoing citations; query removed as citer; dedupe preprint/published versions; only citers published before the query; only non-test citers.
* [x] 5.3 Unit tests for each leakage rule (small synthetic graph).
   * *`research/tests/test_cograph.py`, 11 tests; run inside `v2/08_build_corpus_graph.ipynb`.*
* [ ] 5.4 Leakage canary run (query refs included on purpose) and normal run; report the gap.
* [ ] 5.5 Random-graph control with the same degree distribution.
* [ ] 5.6 GRIT-style expansion (seed top t%, replace bottom b%; tune t, b on dev).
* [ ] 5.7 LADR-style variant (lexical seeds + kNN graph exploration).
* [ ] 5.8 LLM reranker on the expanded lists; end-to-end MRR / nDCG.
* [ ] 5.9 Attribution: share of recovered positives found via the graph.
* CHECKPOINT 5: before/after table for the cascade.

## Phase 6 (optional): Human-centered trust study

* [ ] 6.1 Export thumbs-up/down feedback; relate it to offline scores.
* [ ] 6.2 Design a small study: LLM recommendation with vs without explanation vs similarity score.
* [ ] 6.3 Ethics/consent check with my advisor before recruiting anyone.

## Phase 6B: Researcher-level evaluation on BOUN data (the app's task)

Added 2026-10-12; see `IMPROVEMENT_IDEAS.md`, Idea F. Not started; each fetch or run needs approval first.

* [ ] 6B.1 Data-quality audit of `research/data/cleaned/boun.csv`, reusing `audit/data_quality.py`: strong vs weak non-abstract flags, missing abstracts (1,605 of 4,608 rows have none), and a duplicate-record check.
* [ ] 6B.2 Build the researcher-level eval set with a time split: profiles = BOUN papers before T; candidates = followed-institution papers before T; positives = candidates cited by the researcher's papers after T. Leakage rules and their unit tests as in Phase 5.
* [ ] 6B.3 Benchmark profile aggregation (max vs mean) and the v2 stage-1 methods, then the deployed pointwise Llama stage 2 against stage 1 alone.
* [ ] 6B.4 Relate the offline results to the app's thumbs-up/down feedback (with 6.1).
* CHECKPOINT 6B: researcher-level results table; answer for `APP_NOTES.md` on whether stage 2 helps.

## Phase 7: Write-up

* [x] 7.1 `research/audit/BEFORE_AFTER.md`: v1 vs v2 for every claim in the README.
* [x] 7.2 Update README only after I approve the numbers; keep a "v1 audit" section.
   * *Approved 2026-10-12. The README carries a correction notice and links to AUDIT.md and BEFORE_AFTER.md.*
* [x] 7.3 Fill in the TBD pitch sentences in IMPROVEMENT_IDEAS.md.
   * *Filled where v2 has the numbers. Sentences that depend on Phase 4/5 keep their TBDs.*
* [x] 7.4 One-page summary for my MS advisor and PhD applications. *(`research/audit/SUMMARY.md`)*
