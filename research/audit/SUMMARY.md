# Does LLM reranking help scientific paper recommendation? An audit and a clean re-evaluation

Sena Öz · M.S. Software Engineering, Boğaziçi University · SWE 599 · October 2026

![System overview: v1 audit, v2 pipeline, local models, results and the deployed app](../../docs/figures/system_overview.svg)

**Question.** I built a recommender that suggests new papers from followed institutions to Boğaziçi researchers. Its design is embedding retrieval followed by reranking with a small local LLM (Llama 3.2 3B). Does the reranking step actually help?

**v1 said yes; an audit showed it was an artifact.** My first benchmark ranked each query paper's cited references among random distractors. It reported the LLM far ahead of embeddings (MRR 0.84 vs 0.51). Auditing my own code found nine problems (AUDIT.md, F1–F9):
- candidates were always shown positives-first;
- the prompt's format example pointed at a positive;
- parse failures fell back to that order;
- a DataFrame label/position bug gave positive candidates *other papers' text*, which pushed every non-LLM method to chance;
- plus mis-normalized nDCG, unreproducible seeds, and a wrong pooling choice for SPECTER2.

**v2: a controlled protocol.**
- Candidates are fetched by OpenAlex id with asserted identities and identical fields.
- Negatives are other papers' cited works, published before the query and sharing no author with it. There are two difficulty levels: random, and concept-matched.
- Candidates are shuffled per query and seed.
- Prompts are neutral, and every LLM call's status is logged.
- Settings were tuned on 50 dev queries and results are reported on 118 test queries.
- LLM methods run with 5 shuffle seeds. Statistics are bootstrap CIs and Holm-corrected Wilcoxon tests.
- All models are local: llama.cpp and sentence-transformers. 13 methods in total.

| R-precision % (test) [95% CI] | random negatives | concept-matched |
|---|---|---|
| Qwen3-Embedding-8B | **87.0** [84.2, 89.7] | **80.1** [77.0, 83.0] |
| MiniLM (22M parameters) | 83.3 | 75.7 |
| Llama 3.2 3B, pointwise | 78.8 | 73.9 |
| Two-stage: Qwen3 → listwise Llama reranking | 74.0 | 69.7 |
| Llama 3.2 3B, listwise (v1's "winner") | 43.9 [41.9, 46.0] | 42.0 [40.2, 43.9] |
| Random ranking | 33.3 | 33.3 |

**Findings**
1. **The LLM's advantage was position bias.** Changing nothing but candidate order, listwise Llama gets MRR 0.95–0.98 with positives first and 0.27–0.33 with positives last, below chance. On shuffled candidates it ranks last of 13 methods. It truncates 38% of its rankings.
2. **Listwise reranking hurts the two-stage cascade.** Stage 1 already keeps 89–93% of the cited references in its top 10, yet Llama reranking lowers R-precision by 10–13 points (p ≤ 3·10⁻¹⁰).
3. **Small embedding models nearly match large ones.** MiniLM is within 3.7 / 4.3 points of an 8B embedding model. Pointwise LLM scoring is the only LLM variant that beats lexical baselines.
4. **The audit is reproducible.** Every v1 number in the audit is reproduced by a script. The v2 benchmark runs as six notebooks (01–06) with sanity checks for each audit finding.

**Phase 5: a realistic setting** (notebooks 07–12). Each query is ranked against 11,967 papers instead of a pool of at most 42. A co-citation graph is built under explicit leakage rules, each with a unit test, a canary and an ablation (test, 118 queries):
- **Full-corpus retrieval is much harder.** Qwen3-Embedding recall@100 is 64.0% [58.7, 69.4], BM25 38.7%, and R-precision falls from 87.0% to 25.1%.
- **Leakage-controlled co-citation expansion adds nothing significant:** +0.8 recall@100 [−0.4, +2.1].
  - The canary (the query's own references added on purpose) gives +5.8.
  - The rules catch real leaks, such as a 2012 record of a review with all 10 of a 2020 query's references, and year-only dates on 24% of citers.
- **Second stage.**
  - Pointwise Llama 3.2 3B halves nDCG@10 when used alone (0.340 → 0.175) and changes nothing when fused.
  - Qwen3-Reranker-4B, a model trained for reranking, fused with the embedding score, raises R-precision 25.1 → 28.3 (Holm p = 0.040) and nDCG@10 0.340 → 0.360 (not significant after Holm).

**Limitations.**
- Citation is a proxy for relevance; there are no human judgments yet.
- Concept-matched negatives often share only a broad field label.
- One small general LLM (Llama 3.2 3B) and, in Phase 5, one trained reranker (Qwen3-Reranker-4B) were tested.
- Pretraining contamination could not be tested (one test query after Llama's cutoff; Qwen3-Reranker-4B postdates all queries).
- About 6% of OpenAlex abstracts are not real abstracts. Results are unchanged without them.

**Next steps.**
- **Graded relevance from citation intent, with a small human-judgment study** (how often does the citation proxy agree with researchers?).
- **Researcher-level evaluation on the app's own task** (Boğaziçi researchers, time split), including the deployed stage 2 and Qwen3-Reranker-4B.
- **A trust study** on how researchers use LLM vs similarity-based recommendations, using the deployed system's feedback.

*Details:* `research/audit/BEFORE_AFTER.md` (v1 vs v2), `research/audit/AUDIT.md`, `research/audit/PHASE5_DESIGN.md`, `research/v2/` (notebooks, statistics, figures), `docs/DEVLOG.md` (dated log).
