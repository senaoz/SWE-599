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

Check the published baseline losses in `GOLDSTANDARD_DATA.md` against Table 3 of Stelmakh et al. before quoting them.

## Log

- **2026-10-15.** Framing chosen. Citation-only labels judged insufficient. Stelmakh et al. data downloaded and profiled.
- **2026-10-15.** Idea noted: bibliographic coupling (two papers citing the same work) as a relevance signal for new papers; discussion in chat, not yet tested. 79% of BOUN works (6,557 of 8,287) carry `referenced_works` in OpenAlex.
