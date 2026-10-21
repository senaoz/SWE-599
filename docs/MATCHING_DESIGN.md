# Matching design: from the current job to the target flow

**Status: draft for review (2026-10-15).** No code, schema change or embedding run follows from this document until it is approved. Section 7 lists the decisions that are yours.

**Task (restated 2026-10-15, `docs/DEVLOG.md`).** For each new paper from a followed institution, list the Boğaziçi (BOUN) researchers who work on its topic. Relevance is topical expertise: not "would cite it", not "wrote it".

## 1. Summary

The draft target flow holds up against the research and the code, with five corrections:

1. **pgvector cannot index 4,096-dim vectors.** HNSW and IVFFlat take `vector` up to 2,000 dimensions and `halfvec` up to 4,000 (pgvector README, checked 2026-10-15); a column can store up to 16,000. At 7,822 BOUN works an exact scan is cheap, so "search in the database" works today without an index. An ANN index would need fewer dimensions: a smaller model, or Qwen3-Embedding's Matryoshka output (the model card supports user-defined output dimensions from 32 to 4,096) at ≤ 2,000. The model and dimension decision therefore comes **before** the schema PR, because it fixes the column type.
2. **The BOUN index must be per work, not per (researcher, work).** Today a work with *n* BOUN authors is stored and embedded *n* times.
3. **Matches and feedback need a model version**, or thumbs-up/down cannot be tied to the scores the user saw.
4. **The read path is part of any cut-off change.** `backend/routers/papers.py` filters at `min_score = 0.3` and keeps 5 researchers per paper. Changing the scoring without changing this filter is how `app-mtplx-stage2` would have hidden every match (DEVLOG 2026-10-14, finding 5).
5. **There is no offline relevance ground truth for this task.** Citation positives are paused, authorship positives were dropped, and human judgments are out of scope. The offline plan in section 5 is consistency and regression checks, labelled as such. User feedback is the only direct relevance signal.

## 2. The current code

### 2.1 What the matching job does

`backend/services/matching.py`, `run_matching_job`, every `JOB_INTERVAL_HOURS` (6):

1. For each distinct followed institution, fetch OpenAlex works with `from_publication_date` = the institution's cursor (`FetchCursor`, initialised to *today*), at most 200 per run (`openalex.py`, `max_papers=200`).
2. Insert into `fetched_papers`, dropping exact-title duplicates per institution.
3. Embed `"{title} {abstract} {concepts}"` (cut to 2,048 characters) with `qwen3-embedding:latest` via Ollama, falling back to Ollama Cloud. Write the vector into `fetched_papers.embedding` with an f-string SQL `UPDATE`.
4. Load **every** `researcher_papers.embedding` into numpy and compute the full cosine matrix (`sklearn`).
5. Per paper: keep pairs with cosine ≥ `MATCH_THRESHOLD` (0.3), group by researcher, rank researchers by their best work, take the top 10.
6. Stage 2: for each of those 10, call Llama 3.2 3B (`_llm_generate`) with the paper and the researcher's top 5 matching works. `IRRELEVANT` drops the researcher; `RELEVANT x` replaces the cosine score with `x`; failure keeps the cosine score.
7. Insert `paper_researcher_matches` (score, `model="qwen+llama"`, top-5 matched works as JSON, `llm_score`).

`run_stage2_for_unmatched` repeats steps 3–7 for papers with no match.

### 2.2 Gap against the target

| # | Target (draft) | Current code | Gap |
|---|---|---|---|
| 1 | Persistent BOUN index with `model_version` | `researcher_papers` row per (researcher, work), vector per row, no version | Duplicate vectors per co-author; no way to tell which model produced a vector |
| 2 | External side as a stream, never compared with each other | Already the case (new papers × BOUN only) | Cursor starts *today*, so no backfill; `from_publication_date` misses works that OpenAlex indexes late with an older date; cap of 200 per run silently truncates |
| 3 | Work-level retrieval, researcher-level output, matched works as explanation | Work-level cosine, researcher = best work (max), top-5 works stored as JSON | Close already. Aggregation is max over all works above 0.3, not over a top-K; JSON blob instead of rows |
| 4 | pgvector search in SQL | Full table into numpy every run | 4,096 dims cannot be ANN-indexed (section 1); exact `<=>` in SQL is fine at this size |
| 5 | Same model and template both sides; re-embed on change | Same template both sides; Ollama with silent Cloud fallback | Fallback can mix runtimes (APP_NOTES: vectors from different runtimes are not comparable); template differs from the research's best (`tac_600_1500`) |
| 6 | No LLM stage 2 by default | Llama 3.2 3B on the top 10, replaces the score | Remove. Research: pointwise Llama halves nDCG@10 alone and adds nothing fused |
| 7 | Top-K per paper plus a model-specific minimum | Fixed cosine 0.3 in the job **and** in the read path | Both places must change together |
| 8 | Seed from cleaned data, down-weight huge author lists | Seeds from `research/data/cleaned/boun.csv` | `boun.csv` keeps errata/editorials, misses conference papers, cuts author lists at 100 (`BOUN_DATA.md`) |
| 9 | Log feedback for evaluation | `paper_feedback(user, paper, researcher, is_relevant)` | No snapshot of score, rank or model version at click time |

### 2.3 Other issues found while reading

- **Self-matches.** DEVLOG (2026-10-15) counts 311 `boun.csv` works with a co-author from the v1 followed-institution list. Such a work arrives in the stream *and* sits in the BOUN index, so it matches its own BOUN authors at cosine ≈ 1.0. Needs a rule (section 7, D6).
- **Dead or misplaced pieces.** `Researcher.profile_embedding` (mean vector) is computed by the seeder and never used by matching. The backend writes `.npz` caches into `research/data/embeddings_cache/`. `embedding.py` imports `MODEL_MAP`, `OLLAMA_MODEL_MAP`, `MAX_TEXT_CHARS` from `research/src/similarity.py` (APP_NOTES 2026-10-11). `PaperResearcherMatch.model` defaults to `"specter2"`.
- **SQL built with f-strings** for vector updates (`seeder.py`, `matching.py`). Values are floats, so not injectable, but they should be bound parameters through `pgvector`'s type.
- **No migration tool.** `init_db` runs `create_all` plus ad-hoc `ALTER`s. The table rewrite in section 3 is the point to decide whether to introduce Alembic (D9).
- **Split author ids.** OpenAlex splits some people into two ids (e.g. two "Atakisi" ids with 214 and 213 works). The read path hides this by de-duplicating on `display_name`, which also merges different people with the same name.
- **LFS seed in Docker.** `research/data/boun/*.csv.gz` are Git LFS files; the backend image must get the real files, not pointers.

## 3. Schema and migration

All changes below need your approval before they are written (the brief says: ask before any schema change).

### 3.1 BOUN side: works, authorships, researchers

```
boun_works
  openalex_id        text  PK
  title, abstract    text
  tags_text          text            -- OpenAlex tag field used in the template (D7)
  abstract_source    text            -- openalex | none | (crossref | s2 if looked up)
  type               text
  first_date         date            -- earliest version (cleaned data)
  n_authors          int
  large_collaboration bool           -- 100+ authors
  language_flag      text            -- en | tr | mixed | unknown | other
  embedding          vector(D)       -- D fixed by D1
  embedding_version  text            -- see 3.4

boun_authorships
  work_id            text  FK boun_works
  researcher_id      text  FK researchers
  PK (work_id, researcher_id)

researchers          -- existing table, profile_embedding dropped
```

This is the shape of `research/data/boun/` already (`boun_works`, `researcher_works`, `researchers`), so the seeder becomes a load of three files. One vector per work: 7,822 vectors instead of 17,198.

### 3.2 External side

`fetched_papers` keeps its shape and gains `embedding_version`. On a model change only papers still in the feed window (proposal: the last 30 days, D8) are re-embedded and rematched; older papers keep their old-version matches, which the read path no longer shows. Re-embedding the whole history is possible but costs the same per paper as a backfill.

### 3.3 Matches and feedback

```
paper_researcher_matches
  paper_openalex_id, researcher_id, embedding_version   PK (all three)
  score              float           -- aggregated researcher score
  rank               int             -- rank of the researcher under this paper
  created_at         timestamptz

match_evidence                       -- replaces the matched_paper_ids JSON
  paper_openalex_id, researcher_id, embedding_version, work_id
  score              float           -- cosine of this BOUN work

paper_feedback  (+ columns)
  embedding_version  text            -- what the user was shown
  score, rank        float, int      -- snapshot at click time
```

`llm_score` is dropped with stage 2. The read path shows only the current `embedding_version`. Old rows stay for evaluation.

### 3.4 What `embedding_version` encodes

One string covering everything that makes two vectors incomparable: model id, runtime and quantization, output dimension, pooling, text template id, query instruction (if any). Example: `qwen3-emb-8b|llama.cpp-q8_0|d4096|last|tac_600_1500|noinstr`.

**Acceptance test for any runtime or model change** (from `lessons.md`, GGUF and pooling): embed 20 fixed works with the new runtime and the reference implementation; cosine between the two vectors of each work must be ≥ 0.99. The EmbeddingGemma GGUF failed exactly this way (correlation ≈ 0).

### 3.5 Search

Exact search in SQL, top-K BOUN works per new paper:

```sql
SELECT id, 1 - (embedding <=> :q) AS cosine
FROM boun_works
WHERE embedding_version = :v
ORDER BY embedding <=> :q
LIMIT :k;
```

At 7,822 rows × 4,096 dims (~128 MB as float32) this is a sequential scan, well under a second. An HNSW index becomes possible only with D ≤ 2,000 (`vector`) or ≤ 4,000 (`halfvec`), and only matters if the BOUN index grows far beyond its current size.

### 3.6 Migration path

1. Add the new tables next to the old ones; old job keeps running.
2. Load the cleaned BOUN data and embed it (long run, needs approval; see 6, PR 4).
3. Switch the job and the read path to the new tables in one PR.
4. Drop `researcher_papers`, `profile_embedding`, `llm_score`, `matched_paper_ids` after a release with no reads from them.

## 4. Target flow, with the open questions answered as proposals

1. **Ingest.** Per institution: OpenAlex works since the cursor, filtered by `from_created_date` (or `from_updated_date`) rather than `from_publication_date`, so late-indexed works are not missed. *To verify: whether `from_created_date` is available on the current OpenAlex plan.* Remove the 200 cap or log when it is hit.
2. **Embed** title + abstract + topics with the template of `embedding_version`. A paper with no abstract is embedded from title + topics, and flagged.
3. **Retrieve** the top K₁ BOUN works (proposal: K₁ = 50) with exact cosine, excluding the paper itself (D6). Match on OpenAlex id, the cleaned data's `duplicate_ids` and DOI, because a preprint in the index can arrive in the stream as its published version under another id.
4. **Aggregate** per researcher. Proposal: score = max cosine over the researcher's retrieved works. Mean of top 3 is the alternative.
   - Median works per researcher is 1 (`BOUN_DATA.md`), so max and mean-of-top-3 differ only for the 1,672 researchers with ≥ 2 works.
   - The real risk is that max favours prolific researchers (more works, more chances of one high cosine). Mean-of-top-3 penalises researchers with one or two works. Decide with the regression checks in 5.2 and with feedback, not by argument.
5. **Cut off.** Keep the top K₂ researchers (proposal: 5, the current `TOP_K_MATCHES`). A floor applied per pair would be nearly inert: at the 99th percentile of random-pair cosine about 78 of 7,822 random works pass per paper, more than K₁ and K₂ keep anyway. So the floor acts per **paper**: if the paper's best researcher score is below it, the paper shows no researchers ("no BOUN match"). The floor is set per `embedding_version` from a chosen target, e.g. "at most 1 in 20 random papers gets a match", derived from the best-match distribution of random (paper, BOUN index) pairs, so it carries over when the model changes. Same constant in the job and the read path.
6. **Store** matches and evidence rows with the version.
7. **Show** the researchers with their matched works (evidence rows), as now.
8. **Feedback** stores the version, score and rank shown.

**No stage 2.** A reranker comes back only after it shows a gain on the app's own checks (5.2) and on feedback. The only candidate with evidence is Qwen3-Reranker-4B fused with the embedding score (+3.2 R-precision, Holm p = 0.040, on a different task).

**From `app-mtplx-stage2`, salvage** the discipline, not the code path: a strict score-only parser that logs failures, an LLM floor separate from the cosine floor, and the unit tests. The branch is otherwise not merged.

### Model choice

- Qwen3-Embedding-8B was best in every benchmark, MiniLM within about 4 R-precision points (v2) at a fraction of the cost.
- 0.6B and 4B Qwen3-Embedding were not tested. Matryoshka truncation of 8B was not tested.
- **Query instruction prefix.** The model card asks for a one-sentence instruction on queries (`Instruct: {task}\nQuery:{query}`) and none on documents. The research never used one (same text format both sides), so all reported numbers are without it. Worth one measured comparison on the 5.2 checks (it cannot be judged for relevance offline); if adopted, it goes into `embedding_version`.
- The full 7,822-work re-embed is the cost of any model change. Measure throughput on 200 works first and report the estimate before the full run.

### Data handling

- **Large collaborations.** 1,004 works have 100+ authors; 311 researchers have only such works. Zero weight would remove those 311 from the app entirely. Proposal: keep them, and multiply a work's cosine by a factor < 1 when it has 100+ authors (D4).
- **Missing abstracts.** 1,237 works have none, and the 591 Crossref/S2 abstracts are not in the repo. Either embed those from title + topics, or have the seeder look them up at load time and store them in the database only (D5).
- **Turkish and bilingual works** (245 tr, 81 mixed). The research covered English only. Proposal: embed as is, record `language_flag`, and check in 5.2 whether Turkish works ever reach the top K for English papers.
- **Split author ids.** Not merged automatically. Proposal: keep the read-path de-duplication, but on (normalised name, shared works) instead of the display name alone; a manual alias table is the fallback.

## 5. Evaluation plan

### 5.1 What can and cannot be measured

There is no offline ground truth for "researcher X works on this paper's topic". Citation positives (paused) and authorship positives (dropped) define a different task, and human judgments are out of scope. So:

- **Offline checks** below are consistency and regression checks. They catch broken embeddings, version drift and bad cut-offs. They do **not** measure relevance.
- **Relevance** is measured only by feedback (5.3), once there is a database dump (TODO 6B.4).

### 5.2 Offline checks (run on every model, template or aggregation change)

| Check | What it catches | Pass rule (proposal) |
|---|---|---|
| Runtime equivalence | Wrong pooling, broken GGUF, mixed runtimes | 20 works, cosine to reference ≥ 0.99 |
| Self-retrieval | Index or id bugs (the v1 label/position bug) | Each of 200 BOUN works, used as a query, retrieves itself at rank 1 (run without the D6 exclusion, or it fails by construction) |
| Version-to-version stability | Silent large changes | Report overlap@5 of researchers per paper between old and new version on the last month of fetched papers; no pass rule, read by hand |
| Paper-level floor | Cut-off calibration | Best-match score of 1,000 random fetched papers from unrelated fields against the index; the floor meets the chosen target rate (4, item 5) |
| Coverage | Too strict or too loose cut-off | Share of fetched papers with ≥ 1 researcher, and researchers per paper |
| Topic agreement | Gross mismatches | Share of top-5 pairs sharing an OpenAlex primary topic field. Weak and partly circular (topics are in the text); a sanity read only |
| Turkish and collaboration exposure | Data-handling choices in 4 | How often tr works and 100+-author works appear in top-5 evidence |

Optional, only if you want them (you ruled these out as the definition of relevance): authorship leave-one-out and citation positives as **regression canaries**, i.e. "did a change make these numbers much worse", never reported as quality.

### 5.3 Online feedback

- Thumbs up/down per (paper, researcher) with version, score and rank (3.3).
- Report: share of thumbs-up by rank and by score bucket, per version, with bootstrap CIs; a version change is judged on this.
- Volume will be small. Report counts with every number; no claim below a minimum count you set.

## 6. Ordered PRs

Each PR is small and leaves the app working. ⚠ = needs explicit approval before it runs.

1. **Read path and constants.** Move `MATCH_THRESHOLD`/`TOP_K_MATCHES` into one place used by both job and read path. No behaviour change.
2. **Remove stage 2.** Drop `_llm_generate` and the Llama call; store cosine scores only; label matches with the embedding model. Deletes the rematch job's duplicate code path by sharing one function. Tests for aggregation and cut-off on fixed vectors.
3. ⚠ **Schema: works, authorships, versions, evidence, feedback snapshot** (section 3), added next to the old tables. Decide D9 (Alembic) here.
4. ⚠ **Seeder from `research/data/boun/`** plus the embedding runtime decision (D1, D2): load works and authorships, embed once, write `embedding_version`. Long embedding run; throughput measured first.
5. **Search in SQL and job switch, together with the read path and the calibrated floor.** Exact `<=>` top-K₁, aggregation, top-K₂ with floor; read path reads the new tables at the current version. Offline checks 5.2 reported in the PR.
6. **Ingest fixes.** `from_created_date` (if available), cap logging, self-match rule, optional ⚠ backfill (count call per institution first; OpenAlex cost is small, local embedding time is the cost).
7. **Feedback snapshot in the UI flow** and a small export script for 5.3.
8. **Cleanup.** Drop old tables and columns, `profile_embedding`, the `.npz` writes into `research/`, and the `src.similarity` import.

## 7. Decisions needed

- **D1. Model and dimension.** Qwen3-Embedding-8B at 4,096 (exact search only), 8B truncated to ≤ 2,000 (indexable, untested), a smaller Qwen3-Embedding, or MiniLM.
- **D2. Runtime.** Ollama as now, or `llama-server` as in the research (APP_NOTES 2026-10-11). Drop the Ollama Cloud fallback, since it can mix runtimes.
- **D3. Aggregation.** Max (proposal) or mean of top 3.
- **D4. Large collaborations.** Keep with a weight below 1 (proposal), keep at full weight, or exclude (removes 311 researchers).
- **D5. Missing abstracts.** Title + topics only, or a Crossref/S2 lookup at seed time stored in the database only.
- **D6. Self-matches.** Exclude the paper itself (by id, merged duplicate ids and DOI) from retrieval (proposal), or show "co-author" separately.
- **D7. Text template.** App template (t+a+c, 2,048 characters both sides) or the research's best (`tac_600_1500`). In the research, 1,500 characters were the query (the paper looking for matches) and 600 the candidates; in the app that maps to 1,500 for the new external paper and 600 for BOUN works. Proposal: the research template with that mapping. Tag field: the fetcher uses OpenAlex `concepts` (`openalex.py`); the cleaned BOUN data has `concepts`, `topics` and `keywords`. Use the same field on both sides; `concepts` matches the research, but *to verify* that OpenAlex still fills `concepts` for new works, since `topics` superseded it.
- **D8. Backfill.** None, or N months on first follow.
- **D9. Migrations.** Introduce Alembic with PR 3, or keep `init_db` `ALTER`s.
- **D10. Optional canaries.** Whether to add authorship and citation regression canaries to 5.2.
