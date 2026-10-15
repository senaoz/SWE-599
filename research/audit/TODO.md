# SWE-599 v2: TODO Plan

How to use with Claude Code: put this file and `IMPROVEMENT_IDEAS.md` in `research/audit/`. Ask Claude Code to execute one task at a time, tick the checkbox when its acceptance criteria are met, commit, and stop at every CHECKPOINT to report to me.

Global rules:

* Never modify `research/eval_dataset/week3/` (v1 results). New outputs go to `research/eval_dataset/v2/`.
* Never invent numbers. If something can't be computed, say so in the report.
* Estimate runtime and ask before any long Ollama / API run.
* Fix random seeds and log them for every run.

Suggested timing: Phase 0–1 before the Georgetown visit (~Oct 18). Phases 2–5 before December deadlines.

> **Status (2026-10-14).** Phases 0–3 and 7 were done on branch `v2-audit` (PR senaoz/SWE-599#1, merged); Phase 5 on `v2-phase5` (PR senaoz/SWE-599#3). Dated details are in `docs/DEVLOG.md`.
> - **Paths differ from this plan.** The research folder was reorganized. v1 results moved unchanged from `research/eval_dataset/week3/` to `research/v1/results/`, byte-identical to tag `v1-results`. v2 outputs live in `research/v2/`: notebooks `01`–`06` (v2) and `07`–`12` (Phase 5), `eval_sets/`, `runs/`, `corpus/`, `runs_corpus/`, `stats/`, `figures/`.
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
   * *Dropped (user decision, 2026-10-15): the project will have no human evaluation.*
* [ ] 4.6 Optional: LLM judge, only reported with its agreement against the human subset.
   * *With 4.5 dropped, an LLM judge cannot be validated against humans; any LLM-judge result must be reported as unvalidated.*
* CHECKPOINT 4: benchmark v2 card (size, label distribution, agreement numbers).

## Phase 5: Full-corpus retrieval + leakage-controlled graph expansion

> **Status (2026-10-14).** Done on branch `v2-phase5` (PR senaoz/SWE-599#3): notebooks 07–12 in `research/v2/`, design and decisions in `PHASE5_DESIGN.md`, dated details in `docs/DEVLOG.md`. Corpus: 13,572 citers, 11,967 candidate works (12,096 records before merging duplicates); labels for 48 dev / 118 test queries. Per-task results are in the notes below.

* [x] 5.1 Full-corpus first stage over ~10k papers; recall at k up to 100.
   * *`v2/09_full_corpus_retrieval.ipynb`: 11,967-work corpus, 118 test queries. Qwen3 recall@100 is 64.0% [58.7, 69.4], BM25 38.7%; the degree-only probe gets 2.4% (random 1.3%).*
* [x] 5.2 Co-citation graph builder with leakage rules: no query outgoing citations; query removed as citer; dedupe preprint/published versions; only citers published before the query; only non-test citers.
* [x] 5.3 Unit tests for each leakage rule (small synthetic graph).
   * *`research/tests/test_cograph.py`, 14 tests (22 in total with `test_expansion.py` and `test_rerank.py`); run inside `v2/08_build_corpus_graph.ipynb`.*
* [x] 5.4 Leakage canary run (query refs included on purpose) and normal run; report the gap.
   * *`v2/10_graph_expansion.ipynb`: canary +5.8 [+3.6, +8.2] recall@100 vs +0.8 [−0.4, +2.1] under all rules; rule-by-rule ablations +0.8 to +1.1.*
* [x] 5.5 Random-graph control with the same degree distribution.
   * *Curveball rewiring of pool citers, 5 seeds: −0.5 to −0.9 recall@100.*
* [x] 5.6 GRIT-style expansion (seed top t%, replace bottom b%; tune t, b on dev).
   * *Dev choice t = 5, b = 10%, raw counts; test +0.8 points recall@100, not significant (Holm p = 1.0).*
* [x] 5.7 LADR-style variant (lexical seeds + kNN graph exploration).
   * *BM25 seeds + Qwen3 kNN (k = 32): 62.3% vs 64.0% exhaustive, scoring 12.5% of candidates.*
* [x] 5.8 LLM reranker on the expanded lists; end-to-end MRR / nDCG.
   * *`v2/11_end_to_end.ipynb`: pointwise Llama 3.2 3B on Qwen3-Embedding and expanded top-100 lists. Llama alone: nDCG@10 0.340 → 0.175 (Holm p = 3.1e-11); fused (α = 0.1, dev): −0.004, n.s. Qwen3-Reranker-4B (`v2/12_qwen3_reranker.ipynb`), fused α = 0.8: nDCG@10 +0.021 [+0.001, +0.041] (Holm 0.22), R-precision +3.2 [+1.2, +5.2] (Holm 0.040).*
* [x] 5.9 Attribution: share of recovered positives found via the graph.
   * *First stage: 20 of 548 positives in the expanded top 100 (3.6%) came via the graph. After fused reranking: Llama, none in the top 10 or 20; Qwen3-Reranker-4B, none in the top 10 and 3 in the top 20.*
* CHECKPOINT 5: before/after table for the cascade. *(Shown 2026-10-14; the user approved the numbers, and they are in the README's Phase 5 section.)*

## Phase 6 (optional): Human-centered trust study

* [ ] 6.1 Export thumbs-up/down feedback; relate it to offline scores.
* [ ] 6.2 Design a small study: LLM recommendation with vs without explanation vs similarity score.
* [ ] 6.3 Ethics/consent check with my advisor before recruiting anyone.
   * *6.2–6.3 dropped (2026-10-15): no human evaluation. 6.1 uses feedback the app already records and stays open; it needs a database dump.*

## Phase 6B: Researcher-level evaluation on BOUN data (the app's task)

Added 2026-10-12; see `IMPROVEMENT_IDEAS.md`, Idea F. Each fetch or run needs approval first.

> **Status (2026-10-15).** 6B.1 is done. The app's task was restated (`docs/DEVLOG.md`, 2026-10-15): for a new followed-institution paper the app lists BOUN researchers who work on its topic, so relevance means topical expertise, not "would cite" and not "wrote it". 6B.2–6B.3 as written below (citation positives) are paused; a new design is open. 6B.4 is blocked until a database dump is available.

* [x] 6B.1 Data-quality audit of `research/data/cleaned/boun.csv`, reusing `audit/data_quality.py`: strong vs weak non-abstract flags, missing abstracts (1,605 of 4,608 rows have none), and a duplicate-record check.
   * *Done 2026-10-15 by a full OpenAlex refetch (all work types), cleaning and comparison with `boun.csv`: `audit/BOUN_DATA.md` (data card, generated by `audit/boun_data_report.py`), data in `research/data/boun/`. `boun.csv` (the app's seed) is unchanged.*
* [ ] 6B.2 Build the researcher-level eval set with a time split: profiles = BOUN papers before T; candidates = followed-institution papers before T; positives = candidates cited by the researcher's papers after T. Leakage rules and their unit tests as in Phase 5.
* [ ] 6B.3 Benchmark profile aggregation (max vs mean) and the v2 stage-1 methods, then the deployed pointwise Llama stage 2 against stage 1 alone.
* [ ] 6B.4 Relate the offline results to the app's thumbs-up/down feedback (with 6.1).
* CHECKPOINT 6B: researcher-level results table; answer for `APP_NOTES.md` on whether stage 2 helps.

## Phase 7: Write-up

* [x] 7.1 `research/audit/BEFORE_AFTER.md`: v1 vs v2 for every claim in the README.
* [x] 7.2 Update README only after I approve the numbers; keep a "v1 audit" section.
   * *Approved 2026-10-12. The README carries a correction notice and links to AUDIT.md and BEFORE_AFTER.md.*
* [x] 7.3 Fill in the TBD pitch sentences in IMPROVEMENT_IDEAS.md.
   * *Filled where v2 has the numbers (2026-10-12) and with Phase 5 numbers (2026-10-14). The sentence that depends on Phase 4.5 (human judgments) keeps its TBD.*
* [x] 7.4 One-page summary for my MS advisor and PhD applications. *(`research/audit/SUMMARY.md`)*
