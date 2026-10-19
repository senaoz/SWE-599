# Paper notes (shared working notes)

Running notes for turning the project into a paper. Other sessions: read this first, and add dated entries at the bottom instead of rewriting the decisions above them. Details live in `docs/DEVLOG.md`; this file keeps only what the paper needs.

## Decisions so far (2026-10-15)

- **Framing: benchmark paper, with position bias as the headline finding.**
  - The paper is "Does LLM reranking help scientific paper recommendation?", with 13 methods, two negative types and the full corpus.
  - Headline: the listwise LLM's apparent win came from candidate order. MRR is 0.95 with positives first and 0.33 with positives last, and the median Spearman correlation between input and output order is 0.98.
  - Fallback if space is tight: a reproducibility-track paper about auditing our own evaluation (v1 findings F1–F9).
- **App development continues separately.** The paper is written in parallel. Unfinished app work, the BOUN topical-relevance evaluation and MTPLX stage 2 stay out of the paper unless they are completed.
- **"Citation = relevant" is not enough as the only label.** The paper must show which conclusions survive a human-labelled expertise benchmark (see the next section).
  - **Why.** People cite methods, tools and background, not only topical work. In the MTPLX rubric (DEVLOG 2026-10-14), most citers rated a cited work "same broad field, different topic".
  - **Label-independent claim.** Position bias holds whatever the labels: same model, same candidates, only the order changes.
  - **Label-dependent claim.** The method ranking (embeddings beat LLM reranking) depends on the labels, and is where reviewers will push.
- **No human study of our own.** Use public human-labelled data instead.
- **Open: a larger LLM.** Reviewers will ask whether order-copying is just a property of a 3B Q4 model.
  - Option A: rerun listwise and position bias with Llama 3.1 8B Instruct Q4_K_M. Same family, so only size changes. Qwen3-8B is optional as a second family.
  - Option B: scope the claim to small local LLMs on consumer hardware.
  - Not decided yet.

## Second evaluation: human-labelled expertise (Stelmakh et al.)

**Data.** 58 researchers rated their own expertise (1–5) on 477 papers they had read. Each researcher has a profile of up to 20 of their own papers. The data card is in `research/audit/GOLDSTANDARD_DATA.md` and the local copy in `research/data/external/goldstandard/` (gitignored). We cite the dataset as below.

**Draft methods paragraph:**

> To test whether our conclusions depend on citation-derived labels, we also evaluate on the gold-standard reviewer-expertise dataset of Stelmakh et al. (2025), in which 58 researchers self-reported their expertise (1–5) in reviewing 477 papers they had read. Each researcher is represented by up to 20 of their own papers (the authors' ten sampled profiles, title and abstract). We score each researcher–paper pair with the same methods as in the citation benchmark, aggregate over profile papers by the maximum (as in our deployed system), and report the authors' weighted Kendall-tau loss with their bootstrap confidence intervals, so our numbers are directly comparable to their published baselines. We repeat the position-bias experiment on this data by presenting each researcher's rated papers to the listwise LLM in shuffled, best-first and worst-first order.

**Limits to state in the paper:**
- **Ranking direction.** The dataset ranks papers for one researcher; the app ranks researchers for one paper. Only 13 papers have two raters, so cross-researcher calibration is untested.
- **Domain.** Almost all CS / ML.
- **Contamination.** Every rated paper is from 2022 or earlier, before the model cutoffs, and the labels have been public since 2023.
- **Size.** Only 58 researchers, so CIs will be wide.

**Planned runs** (none done yet):
1. Embeddings and lexical methods. Fast, no LLM.
2. Listwise Llama under three orders (58 calls per condition and seed).
3. Pointwise Llama and Qwen3-Reranker-4B. Measure speed first and ask before long runs.

### Bibliographic coupling on the gold standard (2026-10-15, notebook 14)

Pre-registered before scoring: IDF-weighted cosine coupling over OpenAlex reference lists, max over profile papers; fusion parameters by leave-one-participant-out; Holm within fixed families. References from OpenAlex (profile papers with ≥1 reference: 80.3%, against 33.0% in Semantic Scholar). Pooled loss, 95% participant-bootstrap CI:

| Method | Loss |
|---|---|
| Coupling, IDF-cosine, max (primary) | 0.299 [0.248, 0.348] |
| Qwen3-Embedding-8B, max | 0.222 [0.177, 0.274] |
| SPECTER2 [CLS], max (ours; published 0.221) | 0.231 [0.183, 0.282] |
| MiniLM, max | 0.242 [0.194, 0.292] |
| Coupling + SPECTER2, linear (LOPO) | 0.197 [0.148, 0.247] |
| Coupling + Qwen3, linear (LOPO) | 0.212 [0.164, 0.264] |
| Forward citation (rated paper cites a profile paper) | 0.468 [0.445, 0.488] |
| Reverse citation (selection artefact) | 0.434 [0.403, 0.463] |
| Constant | 0.500 |

- **Alone.** Coupling carries real signal (beats constant for 46 of 58 participants, Holm p = 4.2e-06) but is weaker than every embedding in point estimate; the differences are not significant (Holm p ≥ 0.91).
- **On top of dense.** One of six pre-registered fusion comparisons reached significance: linear fusion with SPECTER2 (−0.035 mean per-participant loss, Holm p = 8.3e-03). The others did not, including fusion with Qwen3-Embedding, the app's model (Holm p = 1.0), and with MiniLM, the weakest embedding, so this is not evidence that coupling helps weaker embeddings in general. For the app, the reportable result is "no significant gain over a strong dense model", matching Phase 5's co-citation result.
- **Forward citation** is rare here: for 40 of 58 participants no rated paper cites a profile paper in any sample (259 of 4,770 participant–paper–sample items are positive), so this dataset barely tests it.
- **Limits.** Published baselines are recomputed from the authors' prediction files; all agree with Table 3 of the paper (arXiv v2) to two decimals. Within-researcher ordering only; almost all CS/ML; 115 of 1,311 papers unmapped and 19.7% of profile papers without references; global IDF weights are nearly flat, so IDF-cosine ≈ cosine.

## Planned paper outline

1. **Introduction.** Deployed two-stage recommender; does LLM reranking help?
2. **Related work.** Listwise / LLM reranking, LLM position bias, scientific document embeddings, citation recommendation benchmarks, reviewer assignment and expert finding.
3. **Citation benchmark (v2).** Construction, leakage rules, negatives, metrics. The audit of v1 is a short subsection or an appendix.
4. **Results.** Method comparison, the position-bias experiment, the two-stage cascade, small vs large embedding models.
5. **Human-labelled expertise evaluation** (Stelmakh et al.). Do the method rankings agree with the citation benchmark?
6. **Full-corpus setting** (Phase 5). Keep it or cut it depending on length.
7. **Limitations and discussion.**

## References to cite

Cite the dataset as:

```bibtex
@article{stelmakh2025gold,
  title   = {A Gold Standard Dataset for the Reviewer Assignment Problem},
  author  = {Stelmakh, Ivan and Wieting, John and Xi, Sarina and Neubig, Graham and Shah, Nihar B.},
  journal = {Transactions on Machine Learning Research},
  year    = {2025},
  url     = {https://arxiv.org/abs/2303.16750},
  note    = {Data: https://github.com/niharshah/goldstandard-reviewer-paper-match (labels CC BY 4.0)}
}
```

Still to find and verify (do not cite from memory):
- RankGPT and listwise LLM reranking.
- LLM position bias and permutation self-consistency in ranking.
- "Lost in the middle".
- SPECTER2 / SciRepEval.
- Citation recommendation benchmarks.
- MTEB-style embedding comparisons.
- Qwen3-Embedding and Qwen3-Reranker.
- GRIT and LADR (Phase 5).
- Co-citation (Small, 1973) and bibliographic coupling (Kessler, 1963).
- Expert-finding datasets: AMiner, Bordea et al. 2013, and LR-Bench / RATE (arXiv 2601.19637).

The published baseline losses in `GOLDSTANDARD_DATA.md` were checked against Table 3 of Stelmakh et al. (arXiv v2) on 2026-10-19; all agree to two decimals.

## Log

- **2026-10-15.** Framing chosen. Citation-only labels judged insufficient. Stelmakh et al. data downloaded and profiled.
- **2026-10-15.** Idea noted: bibliographic coupling (two papers citing the same work) as a relevance signal for new papers; discussion in chat, not yet tested. 79% of BOUN works (6,557 of 8,287) carry `referenced_works` in OpenAlex.
- **2026-10-15.** Bibliographic coupling tested on the gold standard (notebook 14): real signal alone (0.299 vs constant 0.500) but below embeddings; fusion with SPECTER2 significant, with Qwen3-Embedding not.
