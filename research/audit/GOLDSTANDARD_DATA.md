# Stelmakh et al. gold-standard expertise data: data card and fit to our task

Numbers from `research/audit/goldstandard_report.py`, run on a sparse clone of [niharshah/goldstandard-reviewer-paper-match](https://github.com/niharshah/goldstandard-reviewer-paper-match) at commit `00296730` in `research/data/external/goldstandard/` (gitignored).

**Source.** Stelmakh, Wieting, Xi, Neubig, Shah, "A Gold Standard Dataset for the Reviewer Assignment Problem", TMLR 2025 ([arXiv 2303.16750](https://arxiv.org/abs/2303.16750)).
- **Licenses.** Expertise labels are CC BY 4.0 and the code is MIT. Semantic Scholar metadata and paper text stay under their own terms (`LICENSE-DATA.md`), so the data is not committed here.
- **Not downloaded.** Full-text folders (`data/txts`, `evaluation_datasets/d_full_*`, about 2.5 GB).

## What is in it

- **Participants.** 58 researchers, identified by Semantic Scholar author ID.
- **Labels.** 477 self-reported expertise scores, 3–10 per participant (median 9).
  - Each score is on a 1–5 scale in steps of 0.25, and rates the participant's expertise in reviewing a paper they had read.
  - Most scores are high: 4.0 is the most common, and 14 scores are 1.0.
- **Rated papers.** 463 distinct papers, only 13 of them rated by more than one participant. They were published 1973–2022 (median 2020), with title and abstract for every paper. Semantic Scholar marks 458 of 462 as Computer Science.
- **Profiles.** Each participant has a profile of their own papers. `evaluation_datasets/d_20_{1..10}` holds 10 random samples of up to 20 papers per participant (median 19.5), each with title and abstract. No rated paper appears in its rater's profile.
- **Format.** The datasets use the OpenReview affinity format:
  - `submissions.json` maps paper id to title, abstract, year and authors;
  - `archives/~{authorId}.jsonl` holds one profile paper per line.
- **Predictions** are stored as `{reviewer: {paper: score}}`.

## Metric

The metric is computed per participant and is a loss, so lower is better:
- Rank the participant's rated papers by predicted score.
- For every pair of papers with different true scores, add the absolute score difference if the predicted order is wrong, and half of it if the prediction is tied.
- Divide by the sum of all pairwise score differences.

A constant predictor scores 0.5. Only the predicted order matters, not the score values. The official script averages the 10 profile samples and bootstraps participants for a 95% CI.

**Published baselines** (title + abstract; recomputed here from the repository's prediction files with a re-implementation of `scripts/scoring.py`; checked 2026-10-19 against Table 3 of arXiv 2303.16750v2, where every loss agrees to the two decimals printed):

| Method | Loss |
|---|---|
| SPECTER2, max over profile papers | 0.221 |
| SPECTER + MFR | 0.238 |
| SPECTER2, mean over profile papers (Table 3: "Specter2 Mean Pool") | 0.245 |
| o1-mini | 0.245 |
| SPECTER | 0.269 |
| TPMS | 0.281 |
| ACL | 0.296 |
| Claude 3.5 Sonnet | 0.311 |
| ELMo | 0.345 |
| Gemini 2.0 Flash | 0.379 |
| Constant | 0.500 |

## Fit to our task

| | This dataset | Our app |
|---|---|---|
| Relevance | Expertise in reviewing a paper (human, self-reported, graded) | A BOUN researcher works on a new paper's topic |
| Researcher representation | Profile of up to 20 own papers | All of the researcher's BOUN papers |
| Ranking direction | **Papers for one researcher** | **Researchers for one paper** |
| Domain | Almost all CS / ML | All BOUN fields |

- **Usable.** The dataset scores the same function we rank with: how well a researcher's own papers match a new paper.
- **Not measured: comparing researchers.** The app compares scores *across* researchers for one paper; this dataset only orders papers *within* one researcher, since only 13 papers have two raters. Cross-researcher calibration still needs the BOUN-side evaluation.
- **Contamination.** Every rated paper predates the Llama 3.2 and Qwen3 cutoffs, and the labels have been public since 2023.

## How our methods map onto it

All runs use the d_20_1..10 profiles, title + abstract, and write predictions in the official format. Results are directly comparable to the table above.

1. **Embeddings** (Qwen3-Embedding-8B, EmbeddingGemma, SPECTER2 [CLS], MiniLM) and **lexical** (BM25, TF-IDF).
   - Score = max cosine over profile papers, plus mean and top-3 mean as an ablation. Max is what the app uses.
   - No LLM calls, so these runs take minutes.
2. **Pointwise Llama 3.2 3B.**
   - Profile titles + candidate → score.
   - 477 pairs per profile sample, so up to 4,770 calls for all 10 samples. Measure speed first.
3. **Listwise Llama and position bias.**
   - Per participant: profile plus their 3–10 rated papers as a list, ranked under shuffled, best-first and worst-first orders (true expertise defines best and worst).
   - That is 58 calls per condition and seed. This replicates the headline finding on human labels.
4. **Qwen3-Reranker-4B.** Each profile paper is used as a query and the scores are aggregated with max.
5. **Statistics.**
   - The official loss with its bootstrap CI.
   - A per-participant loss for paired Wilcoxon tests with Holm correction, as in v2.
