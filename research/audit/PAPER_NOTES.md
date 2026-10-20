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

**Planned runs** (status 2026-10-20): all done.
1. Embeddings: done (MiniLM, SPECTER2, Qwen3-Embedding; notebook 14). Lexical (BM25, TF-IDF): done (notebook 17).
2. Listwise Llama under three orders: done (notebook 17).
3. Pointwise Llama and Qwen3-Reranker-4B: done (notebook 17).

### LLM reranking on the gold standard (2026-10-20, notebook 17)

Design committed in code before any LLM loss was computed (not a strict pre-registration: lexical losses and timing-probe statuses were seen first): expertise-framed prompts with the v2 structure ("how qualified is this researcher to review…"); listwise and pointwise Llama see the profile titles; Qwen3-Reranker-4B uses each profile paper as the query, max over the profile; lexical methods use profile papers as queries, IDF per profile sample. Listwise uses seeds 1–5, seed s on profile sample d_20_s; its Qwen3 comparison uses the same samples. Pooled loss, 95% participant bootstrap; Holm within each family:

| Method | Loss | vs Qwen3-Embedding, Holm p |
|---|---|---|
| Qwen3-Embedding-8B, max (notebook 14) | 0.222 [0.177, 0.274] | — |
| Qwen3-Reranker-4B, max | 0.268 [0.210, 0.333] | 9.4e-03 (worse) |
| BM25, max | 0.275 [0.216, 0.331] | 1.0e-02 (worse) |
| TF-IDF, max | 0.289 [0.233, 0.349] | 2.4e-03 (worse) |
| Pointwise Llama 3.2 3B | 0.337 [0.282, 0.395] | 3.9e-04 (worse) |
| Listwise Llama 3.2 3B, shuffled | 0.467 [0.442, 0.493] | 1.6e-07 (worse) |
| Listwise, best-first (true order given) | 0.253 [0.179, 0.328] | not tested |
| Listwise, worst-first | 0.685 [0.604, 0.765] | not tested |
| Constant | 0.500 | |

- **The label-dependent claim holds on human labels.** No LLM method beats the embedding; all are significantly worse, including Qwen3-Reranker-4B, which did help on the citation benchmark when fused (notebook 12; not fused here: the reranker was scored alone).
- **Position bias replicates.** Best-first vs worst-first: −0.333 mean per-participant loss, 43 vs 14 participants, Holm p = 1.4e-05; best- and worst-first vs shuffled both Holm p = 1.8e-04. Shuffled, Llama is barely above the constant, and 35% of its outputs repeat the shown order exactly (Kendall τ with the shown order 0.32 on average). Lists are short (3–10), so exact copies are likelier by chance than on the citation benchmark.
- **Failure rate.** Listwise 3 of 870 partial, none failed; pointwise and reranker all ok.
- **Limits.** As for notebook 14; plus the prompts differ from the citation-benchmark ones (expertise, not citation), and the reranker instruction was written for this task without tuning.

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
- **Coverage sensitivity (2026-10-19).** A title search for the 114 papers with neither DOI nor arXiv id raised profile coverage to 85.2%; coupling 0.292 [0.238, 0.343], coupling + SPECTER2 0.199 (Holm p = 1.6e-02), coupling + Qwen3 0.219 vs 0.222 (Holm p = 1.0). No conclusion changes; the pre-registered run stays the headline.
- **BOUN side (notebook 15, descriptive).** Of 200 new followed-institution papers (15–19 Oct 2026), 101 have OpenAlex references and 52 share ≥ 1 with a BOUN work. 22.9% of coupling's top researchers are in Qwen3's top 10 (coupling top-1 at median rank 17 of 3,648). Sanity check on 110 BOUN works with a followed co-author (earlier works only): own BOUN author in the top 10 for 80.0% (embedding) vs 72.7% (coupling); embedding-only 14, coupling-only 6. Self-citations favour coupling here.
- **Limits.** Published baselines are recomputed from the authors' prediction files; all agree with Table 3 of the paper (arXiv v2) to two decimals. Within-researcher ordering only; almost all CS/ML; 115 of 1,311 papers unmapped and 19.7% of profile papers without references; global IDF weights are nearly flat, so IDF-cosine ≈ cosine.

### Discussion point: coupling as a label — precise when present, silent too often (2026-10-19, corrected by notebook 16)

Bibliometrics often treats coupling as a relatedness ground truth. Notebook 16 (post-hoc, exploratory, on notebook 14's pre-registered predictions) tested this on the human ratings. **It overturned part of our first reasoning**, so the point to make in the paper is narrower:
- **Strong coupling is a high-precision positive.** Pooled over items, the top decile of non-zero coupling has mean rating 4.50 [4.26, 4.69] and 88% rated ≥ 4, against 3.71 and 56% overall; the same number of top Qwen3 items: 4.30 [3.99, 4.58], 82% (CIs overlap). Within participants, the top-1 paper by coupling is rated as high as the top-1 by Qwen3 (4.39 vs 4.37, Wilcoxon p = 0.59; random pick 3.75).
- **The weakness is silence, not wrong signal.** 30% of rated items share no reference with the profile (mean rating 3.43); they tie, and that is most of coupling's full-ranking loss (0.299 vs Qwen3 0.222). On pairs where both papers have signal, coupling's loss is 0.233 vs Qwen3's 0.259 (notebook 14, stratified).
- **Our "reversal" inference was wrong.** With coupling scores as the label, Qwen3 is still best (0.212 [0.167, 0.264]); only SPECTER2 and MiniLM swap. The human ratings themselves predict the coupling order worse (0.245) than Qwen3 does, i.e. coupling and humans disagree in ways Qwen3 partly shares with coupling.
- **So, for the paper:** coupling is not usable as a *full-ranking* label (partial and non-random coverage: 52 of 200 new BOUN-side papers have any shared reference; venue, language and field gaps; self-citation bias), but strong coupling is a defensible **silver positive set** (high precision, unknown recall), e.g. for regression canaries or as positives in a precision-oriented check. On BOUN data this is untested for non-CS fields.
- **Why the test is fair:** the human ratings are independent of citations; on citation-labelled benchmarks a citation-derived signal is partly circular (Phase 5 needed leakage rules).
- **Caveats.** a1 pools participants whose score scales differ; the notebook is post-hoc; CS/ML only.

## Planned paper outline

1. **Introduction.** Deployed two-stage recommender; does LLM reranking help?
2. **Related work.** Listwise / LLM reranking, LLM position bias, scientific document embeddings, citation recommendation benchmarks, reviewer assignment and expert finding.
3. **Citation benchmark (v2).** Construction, leakage rules, negatives, metrics. The audit of v1 is a short subsection or an appendix.
4. **Results.** Method comparison, the position-bias experiment, the two-stage cascade, small vs large embedding models.
5. **Human-labelled expertise evaluation** (Stelmakh et al.). Do the method rankings agree with the citation benchmark?
6. **Full-corpus setting** (Phase 5). Keep it or cut it depending on length.
7. **Limitations and discussion.** Includes: coupling as a label — precise when present, silent too often (see the discussion point above).

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
- **2026-10-19.** Table 3 check passed; title-search coverage sensitivity leaves every coupling conclusion unchanged.
- **2026-10-19.** BOUN-side coupling description (notebook 15): coupling and Qwen3 mostly pick different researchers; on the self-author sanity check the embedding finds more.
- **2026-10-19.** Discussion point added: bibliographic coupling is a signal, not a label (agrees with humans less than the embeddings it would judge; partial, biased coverage).
- **2026-10-19.** Notebook 16 corrected the coupling-as-label point: strong coupling is a high-precision positive (top decile 88% rated ≥ 4); the predicted ranking reversal did not happen (Qwen3 best under coupling labels too).
- **2026-10-20.** LLM and lexical methods on the gold standard (notebook 17): no LLM method beats Qwen3-Embedding; listwise position bias replicates on human labels.
