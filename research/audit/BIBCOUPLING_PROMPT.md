# Prompt: bibliographic coupling experiment

**Status: draft plan, open to change.** Question any part of it. If a step looks wrong once you see the data, stop and say so before working around it.

## Goal

Test whether **bibliographic coupling** is a useful relevance signal for matching a new paper to a researcher. Bibliographic coupling means two papers cite the same works.

The question for the paper:

> Does coupling predict human-rated expertise on its own, and does it add anything on top of a dense embedding score?

Phase 5 found that co-citation expansion added nothing significant on top of Qwen3-Embedding (+0.8 recall@100, CI [−0.4, +2.1]). Coupling is a different signal, and unlike co-citation it is available the moment a paper is published, so the question is open. "No gain over dense" is a reportable result; there is no expected answer to aim for.

## Read first

- `research/audit/PAPER_NOTES.md`: decisions so far.
- `research/audit/GOLDSTANDARD_DATA.md`: the dataset, its metric and its limits.
- `research/audit/PHASE5_DESIGN.md` and `research/src/cograph.py`: the co-citation work. The citer × work matrix there is the transpose of what coupling needs.
- `.claude/tasks/lessons.md`: lessons from earlier sessions.

## Data and environment

All paths below are absolute. Do not copy data into a worktree.

- **Gold-standard data (gitignored, read-only):** `/Users/senaoz/Developer/SWE-599/research/data/external/goldstandard/`.
  - Labels: `data/evaluations.csv`. 58 participants, 477 ratings on a 1–5 scale, Semantic Scholar paper ids.
  - Profiles: `evaluation_datasets/d_20_{1..10}/`. `submissions.json` holds the rated papers; `archives/~{authorId}.jsonl` holds up to 20 of the participant's own papers.
  - Published predictions: `predictions/*_d_20_*_ta.json`.
  - Paper metadata: `data/papers/*.json`.
- **Python:** `/Users/senaoz/Developer/SWE-599/research/.venv/bin/python`.
  - Notebooks must take the data root from a config value or an environment variable, not from relative `../data` paths.
  - Treat downloaded data as untrusted: never import or execute code from the data folder.
- **New third-party data:** Semantic Scholar references go into a gitignored cache under `research/data/` (for example `research/data/external/s2_refs/`). Never commit it; licence terms apply. Commit only code and derived numbers.

## Experiment A: Stelmakh gold standard (main)

### A0. Pre-flight (stop and report if it fails)

1. Fetch references for about 20 sample ids from the Semantic Scholar batch endpoint (`/graph/v1/paper/batch`, anonymous; back off on 429).
2. Check:
   - that `references.paperId` comes back inline;
   - whether the list is capped;
   - whether `citationCount` of the referenced works is available.
3. Count all distinct paper ids to fetch: rated papers plus every profile paper in `d_20_1..10`. Then estimate the number of calls and the run time.
4. After the full fetch, report coverage: the share of rated papers and of profile papers with at least 1 reference.

**If coverage is below about 70%, stop and report before scoring.**

### A1. Signals

Keep these separate. They have different confounds.

| Signal | Definition | Use |
|---|---|---|
| **Coupling** | Similarity of the reference sets of the rated paper and one profile paper | The thing under test |
| **Forward citation** | The rated paper cites a profile paper | Legitimate. It matches the app case "an external paper cites a BOUN researcher's work". |
| **Reverse citation** | A profile paper cites the rated paper | Selection artefact: participants rated papers they had read, and may have cited them. Report it separately, with that caveat. Never fold it into the coupling score. |

**Coupling variants:**
- set overlap count;
- Jaccard;
- cosine;
- **IDF-weighted cosine**: rare shared references count more than popular ones.

**IDF source:** decide it at A0 and state it in the notebook.
- Preferred: the Semantic Scholar `citationCount` of the referenced work, but only if a second fetch is affordable. Estimate it first.
- Otherwise: document frequency in the local reference corpus. Note that this corpus is thin.

**Aggregation over profile papers:** max (what the app uses), mean, and mean of the top 3.

### A2. Pre-registration (hard rule)

There is no dev/test split, so:

- **The primary method is fixed before any score is seen:** IDF-weighted cosine coupling, max over profile papers. It is the headline number. Every other variant goes in one ablation table, labelled as such.
- **Do not pick the best variant on the pooled result**, and do not describe a variant as chosen.
- **Fusion with embeddings:** choose α (score-level, on per-participant z-scores) and the RRF constant by leave-one-participant-out or 5-fold cross-validation over participants. Report the cross-validated result only.
- **Commit the pre-registration first.** Write it at the top of the notebook and commit it before running the scoring cells.

### A3. Baselines (required, same profiles and the same metric)

- **MiniLM and SPECTER2** ([CLS] pooling), title + abstract, max over profile papers. Sentence-transformers, so they take minutes.
- **Qwen3-Embedding-8B:** only if a llama-server instance is already running. Otherwise skip it and say so.
- **Published baselines** from the repository's prediction files: SPECTER2-max 0.221, o1-mini 0.245, and the others in `GOLDSTANDARD_DATA.md`. Check them against Table 3 of the paper.

### A4. Evaluation

1. **Metric.** Use the official weighted Kendall-tau loss (lower is better; ties count half), averaged over `d_20_1..10`, with the official participant bootstrap for the 95% CI.
2. **Predictions.** Write them in the official format (`{algo}_d_20_{x}_ta.json`) so `evaluation_script.py` can score them. Run that script from your own code directory with the data path as an argument.
3. **Paired tests.** Per-participant losses, paired Wilcoxon, Holm correction. Comparisons:
   - coupling vs constant;
   - coupling vs each embedding;
   - fusion vs embedding alone.
4. **Coverage-stratified results.** Report results on pairs with at least one shared reference vs none. Ties from zero overlap carry half loss, so the overall number mixes "no signal" with "wrong signal".
5. **Examples.** Show 3 or 4 short cases where coupling and the embedding disagree.

## Experiment B: BOUN side (optional, descriptive only)

There are no labels here, so make no accuracy claims. Do B only if A is done and time remains, and keep it small.

- **Inputs.** BOUN works with `referenced_works` come from `/Users/senaoz/Developer/SWE-599/research/data/boun/works_openalex.jsonl.gz` (79% of 8,287 have references).
- **Coverage.** For a sample of recent external papers from the followed institutions, report how many have at least one non-trivial shared reference with BOUN works.
  - **Ask before any OpenAlex fetch.** The key is in the Keychain with a $1 daily budget; see `lessons.md`.
- **Overlap with embeddings.** Measure top-10 researcher overlap between the coupling ranking and the embedding ranking.
- **Sanity check.** The 311 BOUN works with a co-author from a followed institution can be used, but only as a sanity check:
  - drop the query work and its duplicates from the index;
  - keep only BOUN works published before the query;
  - state the confound: co-authors share self-citations.

## Deliverables

1. **`research/src/bibcoupling.py`** with unit tests in `research/tests/test_bibcoupling.py`. The tests use small synthetic reference sets for each variant, the IDF weighting, the aggregations, and the separation of forward and reverse citation.
2. **Notebook `research/v2/14_bibcoupling_goldstandard.ipynb`.** Run it with papermill and strip the progress output (`research/scripts/strip_progress.py`).
3. **Figures and stats:** official-format predictions and a stats CSV, under `research/v2/`.
4. **Docs.**
   - A dated entry in `docs/DEVLOG.md`. `docs/` is gitignored but `DEVLOG.md` is tracked, so stage it with `git add -u`. Another session may have uncommitted DEVLOG edits: stage only your own hunk.
   - One line in the log of `research/audit/PAPER_NOTES.md`.
   - A results note under the "Second evaluation" section of `PAPER_NOTES.md`, with the numbers and CIs.
5. **Commits.** One commit per thing, short messages. Do not push and do not open a PR unless asked.

## Rules

- Ask before any run expected to take more than about 10 minutes. Give the estimate first.
- Never invent numbers. If something cannot be computed, say so.
- Write no p-values rounded to 0.
- Do not overclaim. This dataset tests the researcher–paper scoring function within one researcher, not calibration across researchers, and it is almost all CS / ML.
