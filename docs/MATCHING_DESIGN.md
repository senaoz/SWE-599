# Matching design: from the current job to the target flow

**Status (updated 2026-10-21).** Drafted 2026-10-15; decisions D1–D10 made 2026-10-21 (section 8); PRs 1 and 2 merged (senaoz/SWE-599#6, #7), plus vector binding through pgvector's type (#8). PRs 3–5 were done as one rebuild (2026-10-21), since there was no data to migrate. Sections 2.1 and 2.2 describe the code before the rebuild. Long embedding runs and backfills still need explicit approval.

**Task (restated 2026-10-15, `docs/DEVLOG.md`).** For each new paper from a followed institution, list the Boğaziçi (BOUN) researchers who work on its topic. Relevance is topical expertise: not "would cite it", not "wrote it".

## 1. Summary

**What the research says for the app** (paper draft, `paper/main.tex` on `paper-draft`; `research/audit/PAPER_NOTES.md`). Under shuffled candidate order, no LLM reranker, second stage or citation-graph signal beats Qwen3-Embedding-8B on both label sources (citation labels and the expertise ratings of 58 researchers). The only second-stage gain (Qwen3-Reranker-4B fused with the embedding) appears on citation labels only and is not claimed. A 22M-parameter MiniLM stays within about four R-precision points (gold standard: 0.242 vs 0.222 loss, overlapping CIs). So the target is a single embedding stage, and this document only plans that stage.

The draft target flow holds up against the research and the code, with five corrections:

1. **pgvector cannot index 4,096-dim vectors.** HNSW and IVFFlat take `vector` up to 2,000 dimensions and `halfvec` up to 4,000 (pgvector README, checked 2026-10-15); a column can store up to 16,000. At 7,822 BOUN works an exact scan is cheap, so "search in the database" works today without an index. An ANN index would need fewer dimensions: a smaller model, or Qwen3-Embedding's Matryoshka output (the model card supports user-defined output dimensions from 32 to 4,096) at ≤ 2,000. *Resolved by D1: 4,096 dimensions, exact search.*
2. **The BOUN index must be per work, not per (researcher, work).** Today a work with *n* BOUN authors is stored and embedded *n* times.
3. **Matches and feedback need a model version**, or thumbs-up/down cannot be tied to the scores the user saw.
4. **The read path is part of any cut-off change.** `backend/routers/papers.py` filters at `min_score = 0.3` and keeps 5 researchers per paper. Changing the scoring without changing this filter is how `app-mtplx-stage2` would have hidden every match (DEVLOG 2026-10-14, finding 5).
5. **There is no offline relevance ground truth for the app's direction.** The gold standard ranks papers for one researcher, not researchers for one paper, and it is almost all CS; it supports the choice of model and aggregation, not the app's cut-off or cross-researcher ranking. The offline plan in section 5 is consistency and regression checks, labelled as such. User feedback is the only direct relevance signal for the app's direction.

## 2. The current code

### 2.1 What the matching job does (after PRs 1, 2 and #8)

`backend/services/matching.py`, `run_matching_job`, every `JOB_INTERVAL_HOURS` (6):

1. For each distinct followed institution, fetch OpenAlex works with `from_publication_date` = the institution's cursor (`FetchCursor`; following an institution sets it 14 days back, `routers/institutions.py`), at most 200 per run (`openalex.py`, `max_papers=200`).
2. Insert into `fetched_papers`, dropping exact-title duplicates per institution.
3. Embed `"{title} {abstract} {concepts}"` (cut to 2,048 characters) with `qwen3-embedding:latest` via local Ollama only (the Ollama Cloud fallback was removed). Vectors are bound through pgvector's SQLAlchemy type (#8), no longer written with f-string SQL.
4. Load **every** `researcher_papers.embedding` into numpy and compute the cosine matrix (`services/ranking.py`, `cosine_matrix`).
5. Per paper, `rank_researchers` (`services/ranking.py`, shared by both jobs since PR 1): keep rows with cosine ≥ `MATCH_THRESHOLD` (0.3), group by researcher, aggregate with `MATCH_AGGREGATION` (`max` default, or `mean_top3`; D3), keep the top `RAG_RETRIEVE_TOP_K` (10).
6. Insert `paper_researcher_matches` with the cosine score, `model = qwen3-embedding:latest`, the researcher's top-5 matched works as JSON, and no `llm_score` (column kept until PR 8).

No stage 2 since PR 2. `run_rematch_unmatched` reruns steps 3–6 for papers with no match; both jobs share `_embed_and_store` and `_match_and_store`. The read path (`routers/papers.py`) still filters at `min_score = MATCH_THRESHOLD`, keeps `TOP_K_MATCHES` (5) per paper and de-duplicates by `display_name`.

### 2.2 Gap against the target

| # | Target (draft) | Current code | Gap |
|---|---|---|---|
| 1 | Persistent BOUN index with `model_version` | `researcher_papers` row per (researcher, work), vector per row, no version | Duplicate vectors per co-author; no way to tell which model produced a vector |
| 2 | External side as a stream, never compared with each other | Already the case (new papers × BOUN only) | A 14-day backfill on follow (not 30 days, D8); `from_publication_date` misses works that OpenAlex indexes late with an older date; cap of 200 per run silently truncates |
| 3 | Work-level retrieval, researcher-level output, matched works as explanation | Work-level cosine, researcher score by `MATCH_AGGREGATION` (max default), top-5 works stored as JSON | Close already. Aggregation is over all works above 0.3, not over a top-K₁; JSON blob instead of rows |
| 4 | pgvector search in SQL | Full table into numpy every run | 4,096 dims cannot be ANN-indexed (section 1); exact `<=>` in SQL is fine at this size |
| 5 | Same model and template both sides; re-embed on change | Same template both sides; local Ollama only (Cloud fallback removed) | Runtime differs from the research's verified `llama-server` setup (D2); template differs from D7 (title + abstract, no truncation) |
| 6 | No LLM stage 2 by default | Removed in PR 2 | Done |
| 7 | Top-K per paper plus a model-specific minimum | Fixed cosine 0.3 in the job (one shared function since PR 1) **and** in the read path | Both places must change together (PR 5) |
| 8 | Seed from cleaned data, down-weight huge author lists | Seeds from `research/data/cleaned/boun.csv` | `boun.csv` keeps errata/editorials, misses conference papers, cuts author lists at 100 (`BOUN_DATA.md`) |
| 9 | Log feedback for evaluation | `paper_feedback(user, paper, researcher, is_relevant)` | No snapshot of score, rank or model version at click time |

### 2.3 Other issues found while reading

- **Self-matches.** The cleaned data has 642 BOUN works with a co-author from a followed institution, 460 of them 100+-author collaborations (DEVLOG 2026-10-19; `boun.csv` had 311). Such a work arrives in the stream *and* sits in the BOUN index, so it matches its own BOUN authors at cosine ≈ 1.0. Rule: D6.
- **Dead or misplaced pieces.** `Researcher.profile_embedding` (mean vector) is computed by the seeder and never used by matching. The backend writes `.npz` caches into `research/data/embeddings_cache/`. `embedding.py` imports `MODEL_MAP`, `OLLAMA_MODEL_MAP`, `MAX_TEXT_CHARS` from `research/src/similarity.py` (APP_NOTES 2026-10-11). `PaperResearcherMatch.model` defaults to `"specter2"`.
- ~~**SQL built with f-strings** for vector updates.~~ Fixed in #8 (bound through pgvector's SQLAlchemy type; pgvector pinned to 0.5.1).
- **No migration tool.** `init_db` runs `create_all` plus ad-hoc `ALTER`s, including a block that drops and recreates `embedding` columns. Alembic comes with PR 3 (D9).
- **Split author ids.** OpenAlex splits some people into two ids (e.g. two "Atakisi" ids with 214 and 213 works). The read path hides this by de-duplicating on `display_name`, which also merges different people with the same name.
- **LFS seed in Docker.** `research/data/boun/*.csv.gz` are Git LFS files; the backend image must get the real files, not pointers.
- **Production runs Ollama in Docker** (`docker-compose.prod.yml`: `ollama` and `ollama-init` services pulling `qwen3-embedding`). D2's `llama-server` needs its own service there (section 7, O1).

## 3. Schema and migration

All changes below need your approval before they are written (the brief says: ask before any schema change).

### 3.1 BOUN side: works, authorships, researchers

```
boun_works
  openalex_id        text  PK
  doi                text            -- for the self-match rule (D6)
  duplicate_ids      text[]          -- merged duplicate records (cleaned data), for D6
  title, abstract    text            -- abstract only from OpenAlex (D5)
  abstract_source    text            -- openalex | crossref | s2 | none; crossref/s2 text is used
                                     --   for the vector only, never stored or shown (D5)
  type               text
  first_date         date            -- earliest version (cleaned data)
  n_authors          int
  large_collaboration bool           -- 100+ authors
  language_flag      text            -- en | tr | mixed | unknown | other
  embedding          vector(4096)    -- D1
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

One string covering everything that makes two vectors incomparable: model id, runtime and quantization, output dimension, pooling, text template id, query instruction (if any). With D1, D2 and D7: `qwen3-emb-8b|llama.cpp-b11146-q4_k_m|d4096|last|ta_full|noinstr`.

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

None needed: there was no data to keep (user, 2026-10-21), so the rebuild creates the target schema directly. `init_db` stops start-up on a database with the old schema or a wrong embedding dimension, instead of altering or dropping anything.

## 4. Target flow, with the open questions answered as proposals

1. **Ingest.** Per institution: OpenAlex works since the cursor, filtered by `from_created_date` (or `from_updated_date`) rather than `from_publication_date`, so late-indexed works are not missed. *To verify: whether `from_created_date` is available on the current OpenAlex plan.* Remove the 200 cap or log when it is hit.
2. **Embed** `"{title} {abstract}"`, no truncation, the same on both sides (D7). A paper with no abstract is embedded from its title and flagged.
3. **Retrieve** the top K₁ BOUN works (proposal: K₁ = 50) with exact cosine, excluding the paper itself (D6). Match on OpenAlex id, the cleaned data's `duplicate_ids` and DOI, because a preprint in the index can arrive in the stream as its published version under another id.
4. **Aggregate** per researcher with `max` (D3; already a parameter since PR 2). Mean of top 3 is checked in PR 5.
   - Median works per researcher is 1 (`BOUN_DATA.md`), so max and mean-of-top-3 differ only for the 1,672 researchers with ≥ 2 works.
   - On the gold standard, mean-of-top-3 is slightly better within each researcher's profile (Qwen3 0.219 vs 0.222, within the CIs, not pre-registered). The open risk is across researchers: max favours prolific researchers, which the gold standard cannot test.
5. **Cut off.** Keep the top K₂ researchers (proposal: 5, the current `TOP_K_MATCHES`). A floor applied per pair would be nearly inert: at the 99th percentile of random-pair cosine about 78 of 7,822 random works pass per paper, more than K₁ and K₂ keep anyway. So the floor acts per **paper**: if the paper's best researcher score is below it, the paper shows no researchers ("no BOUN match"). The floor is set per `embedding_version` from a chosen target, e.g. "at most 1 in 20 random papers gets a match", derived from the best-match distribution of random (paper, BOUN index) pairs, so it carries over when the model changes. Same constant in the job and the read path.
6. **Store** matches and evidence rows with the version.
7. **Show** the researchers with their matched works (evidence rows), as now.
8. **Feedback** stores the version, score and rank shown.

**No stage 2** (removed in PR 2). A reranker comes back only after it shows a gain on feedback. The evidence against one is now stronger than at drafting time:
- Qwen3-Reranker-4B fused with the embedding helped on citation labels (+3.2 R-precision, Holm p = 0.040) but not on human labels (0.233 vs 0.222, post-hoc); alone it is worse on human labels (0.268).
- Listwise Llama is order-sensitive in a model-dependent direction (3.2 3B favours the first candidates, 3.1 8B the last). Shuffled, both trail the embedding on both label sources.
- Cost: about 0.35 s per pointwise call (3B), 7–9 s per listwise list (3B), about 18 s (8B), against one encoder call per new paper.

**Citation signals** are not part of the scoring. Bibliographic coupling adds nothing significant on top of Qwen3-Embedding (0.212 vs 0.222, Holm p = 1.0), and only 52 of 200 recent followed-institution papers share any reference with a BOUN work. Strong coupling is a high-precision positive (top decile: mean rating 4.50), but D10 keeps it out of the checks for now.

Branch `app-mtplx-stage2` is superseded by PR 2 and can be deleted.

### Model choice (D1, D2)

- Qwen3-Embedding-8B was best on both label sources: R-precision 87.0 / 80.1 on the citation pools, loss 0.222 [0.177, 0.274] on the gold standard. MiniLM is within about four R-precision points and at 0.242 on the gold standard, so it stays the fallback if an 8B model cannot be hosted (O1).
- 0.6B and 4B Qwen3-Embedding were not tested. Matryoshka truncation of 8B was not tested.
- **Query instruction prefix.** The model card asks for a one-sentence instruction on queries (`Instruct: {task}\nQuery:{query}`) and none on documents. Every number in the research and the paper is without it (a stated limitation of the paper). Worth one measured comparison on the gold standard and the 5.2 checks; if adopted, it goes into `embedding_version` and forces a full re-embed (O3).
- A model change means re-embedding all 7,822 works. Measure throughput on 200 works first and report the estimate before the full run.

### Data handling (D4, D5)

- **Large collaborations** at full weight, flagged by `large_collaboration` (D4). 1,004 works have 100+ authors; 311 researchers have only such works. PR 5's exposure check decides whether a weight is added.
- **Missing abstracts** (D5). Crossref/S2 abstracts (591 works) are used for the vector only; works with no abstract anywhere (1,237) are embedded from the title and flagged.
- **Turkish and bilingual works** (245 tr, 81 mixed). The research covered English only. Embed as is, record `language_flag`, and check in 5.2 whether Turkish works reach the top K for English papers.
- **Split author ids.** Not merged automatically. Proposal: keep the read-path de-duplication, but on (normalised name, shared works) instead of the display name alone; a manual alias table is the fallback.

## 5. Evaluation plan

### 5.1 What can and cannot be measured

There is no offline ground truth for "researcher X works on this paper's topic". Citation positives (paused) and authorship positives (dropped) define a different task, and human judgments are out of scope. So:

- **Evidence for the scoring function** comes from the research: the gold standard (human expertise ratings, within one researcher, CS only) and the citation benchmark agree on the model and on dropping stage 2 (Kendall τ 0.79 between the two label sources over 8 methods). It does not cover the app's direction (researchers for one paper), the cut-off, or non-CS fields.
- **Offline checks** below are consistency and regression checks. They catch broken embeddings, version drift and bad cut-offs. They do **not** measure relevance.
- **Relevance in the app's direction** is measured only by feedback (5.3), once there is a database dump (TODO 6B.4).

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
| Authorship leave-one-out (D10) | Regressions in retrieval through a researcher's other works | BOUN works with a followed co-author as queries, the work itself excluded; share with a BOUN author in the top 10 (Experiment B baseline: 80.0% of 110). A regression signal, never quality |

### 5.3 Online feedback

- Thumbs up/down per (paper, researcher) with version, score and rank (3.3).
- Report: share of thumbs-up by rank and by score bucket, per version, with bootstrap CIs; a version change is judged on this.
- Volume will be small. Report counts with every number; no claim below a minimum count you set.

## 6. Ordered PRs

Each PR is small and leaves the app working. ⚠ = needs explicit approval before it runs.

1. ✅ **Read path and constants** (senaoz/SWE-599#6). The cut-off rule is one function (`rank_researchers`) used by both jobs; no behaviour change.
2. ✅ **Remove stage 2** (senaoz/SWE-599#7). Cosine scores only, `MATCH_AGGREGATION` parameter, shared job code, tests on fixed vectors. Also merged: vector binding through pgvector's type (#8).
3. ✅ **Rebuild, replacing the planned PRs 3–5** (2026-10-21, branch `app-rebuild`): the target schema (section 3) with no migration tool (D9 revised), the seeder from `research/data/boun/` reusing the Experiment B vectors (7,822 of 7,822 hits; live encoding reproduces them at cosine 1.000000 on 20 works), the `llama-server` encoder, exact search in SQL with the self-match rule (D6, moved here from PR 6), the read path at the current version and the feedback snapshot (moved here from PR 7). The calibrated floor and the 5.2 checks are not done: on the first run the 0.3 floor removed no paper (top-1 scores 0.41–0.95), so they are the next matching task.
4. **Calibrated floor and the 5.2 checks**, with the D10 canary and the D4 exposure check. The 0.3 floor removed no paper on the first run.
5. **Ingest fixes.** `from_created_date` (if available, O2), the 200-per-run cap fixed, and the ⚠ 30-day backfill on first follow (D8; following sets a 14-day cursor today).
6. **Feedback export** for 5.3 (the snapshot itself is stored since the rebuild).
7. ✅ **Redesign around the Boğaziçi researcher** (2026-10-22, branch `app-redesign`, on top of #12 and #13). The main user is a Boğaziçi researcher (user decision): an account claims a researcher profile (unverified) and gets a **For me** feed; the institution feed becomes **Explore**. Scores are shown as levels (Strong / Likely / Weak), the matched BOUN work is shown on every card, researchers matched through the same work are grouped, and feedback asks "Works on this topic?" (yes / partly / no, with an optional reason) instead of thumbs; Admin summarizes answers by rank (section 5.3). New paper fields from OpenAlex: work type, field of the primary topic, open-access link.

The planned cleanup PR is no longer needed: the rebuild removed the old tables and columns, `profile_embedding`, the `.npz` writes into `research/` and the `src.similarity` import.

## 7. Open questions

D1–D10 are decided (section 8). Still open:

- **O1. Hosting the encoder in production.** Production runs Ollama in Docker on the VPS. D2 needs a `llama-server` service there with the Q4_K_M GGUF (4.4 GB on disk) and enough RAM; the VPS size is not recorded in the repo. If it cannot host 8B, the fallback is MiniLM (D1), which changes `embedding_version` and needs a full re-embed. Seeding there without the gitignored research cache means embedding all 7,822 works live: about 6 h at the local speed of the first run (2.8 s per text with another 8B model loaded); copying the cache to the server avoids it. Decide before deploying the rebuild.
- **O2.** ~~Whether OpenAlex's `from_created_date` filter is available.~~ Answered 2026-10-22: it needs a paid plan ("Plan upgrade required"). PR 5 has to filter on each work's `created_date` after the fetch instead, which also drops old records with future publication dates (Zenodo uploads dated 2027–2028).
- **O5.** Profile claims are unverified: any account can claim any researcher. Before real users, verify claims (e.g. by the university email or ORCID).
- **Follow-ups from the redesign:** a weekly email digest per researcher, "similar new papers" on the paper page, and department filters (OpenAlex has no departments, so they need a mapping).
- **O3.** Whether to measure Qwen3-Embedding's query instruction prefix (section 4, Model choice). Not planned; it would force a full re-embed.
- **O4.** A full re-embed of the BOUN index needs the gitignored Crossref/S2 abstract cache, which exists only on the author's machine (D5). Keep a backup of it, or accept title-only vectors for those 591 works after a re-embed elsewhere.

## 8. Decisions

Made with the user, one at a time, starting 2026-10-21.

- **D1 (2026-10-21). Qwen3-Embedding-8B at 4,096 dimensions, exact search, no ANN index.** Best on the v2 citation benchmark and on the gold standard (loss 0.222 vs MiniLM 0.242, overlapping CIs; notebook 14), and it is the model the paper reports. Exact scan is fast enough at 7,822 works. MiniLM stays the fallback if hosting cost rules out an 8B model.
- **D2 (2026-10-21). `llama-server` with the research setup:** Qwen3-Embedding-8B Q4_K_M GGUF, `--pooling last`, build b11146 (`research/README.md`). This setup is verified against the cached v2 vectors (cosine 1.0000, DEVLOG 2026-10-15), and it is the setup that produced the Experiment B vectors for all 7,822 works, which PR 4 may reuse if the template matches (D7). Ollama has not been checked. Applies from PR 4; PR 2 keeps Ollama.
- **D3 (2026-10-21). Max, as a parameter of the shared aggregation function; mean of top 3 is checked in PR 5.** On the gold standard (notebook 14) top-3 mean is slightly better than max for all three models (Qwen3 0.219 vs 0.222) but within the CIs and not pre-registered; its direction is papers per researcher, so the prolific-researcher bias across researchers is untested. Max is the current behaviour.
- **D4 (2026-10-21). Large collaborations at full weight for now, with a `large_collaboration` column.** No research measures a weight (the gold standard is CS, without collaborations), so any factor would be a guess; most of the noise is self-matches (D6: 460 of the 642 cleaned BOUN works with a followed co-author are 100+-author works, DEVLOG 2026-10-19). PR 5's exposure check (5.2) decides whether a weight is added.
- **D5 (2026-10-21). Crossref/S2 abstracts are used for the vector only; their text is neither stored nor shown.** Works with no abstract anywhere (1,237) are embedded from the title and flagged (`abstract_source = none`). This is how the Experiment B vectors were built (`src.boun_data.work_texts` falls back to the gitignored Crossref/S2 cache), so it matches D2's reuse plan. Limit: a full re-embed needs that local cache, which exists only on the author's machine.
- **D6 (2026-10-21). Exclude the paper itself from retrieval in PR 6**, matched by OpenAlex id, the cleaned data's duplicate ids and DOI. A "co-author" label for BOUN authors of the new paper is left for later (it needs the new papers' author lists stored).
- **D7 (2026-10-21). Title + abstract on both sides, no truncation, no tag field** (template id e.g. `ta_full` in `embedding_version`). For Qwen3 the template barely matters on v2 dev (R-precision 88.2 / 88.2 / 88.7 on `random` and 81.9 / 81.2 / 81.3 on `concept` for t / ta / tac at 600/1500; `03_dev_tuning.ipynb`); `tac` was chosen by mean rank over all methods, mostly for the lexical ones. This is the Experiment B template (`work_texts`, `sample_text`), so its vectors can be reused, and it drops the open question of whether OpenAlex still fills `concepts`.
- **D8 (2026-10-21). Backfill 30 days on the first follow of an institution, once per institution** (same as the feed window, 3.2), in PR 6 with a count call per institution and the 200-per-run cap fixed (paging or a logged cap). Rough cost from Experiment B (about 40 papers with abstracts per day over the 7 institutions): about 1,200 papers, about 12 list calls ($0.0012), and about 16 min of embedding on the M1 Max; server time unknown. The first backfill runs only after the user approves it.
- **D9 (2026-10-21; revised the same day: no migration tool until there is data to keep, since the app had none).** Originally: Alembic with PR 3: a baseline migration of the current schema, then the new tables. The block in `init_db` that drops and recreates `embedding` columns on a dimension mismatch (`backend/database.py`) is removed; a mismatch stops start-up with an error instead of deleting data.
- **D10 (2026-10-21). Authorship leave-one-out canary only, in PR 5, reported as a regression signal, never as quality.** BOUN works with a followed co-author are used as queries with the work itself excluded (D6 rule); the check is whether a BOUN author is still retrieved in the top 10 through their other works. Experiment B gives the starting point (182 non-collaboration works, 110 with a BOUN author who has an earlier work; own author in the top 10 for 80.0% of queries; DEVLOG 2026-10-19). No citation canary: coverage is partial (52 of 200 followed papers share a reference with a BOUN work) and it needs reference fetches per paper.
