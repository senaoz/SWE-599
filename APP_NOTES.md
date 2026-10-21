# App backlog and ideas

A running log of changes the deployed recommender (`backend/`, `frontend/`) needs, collected while doing the v2 research audit (`research/audit/AUDIT.md`). Research work does not touch the app; these items are for a later, combined update.

Each entry gives the date it was noted, what to do, and why.

## Model serving

- **2026-10-11 — Move off Ollama and drop the cloud fallback.** The research side serves models through a local OpenAI-compatible API (`/v1/chat/completions`, `/v1/embeddings`): Jan at first, and since 2026-10-12 a standalone `llama-server` from llama.cpp (see `research/README.md`). The backend still calls Ollama (`backend/services/embedding.py`) and falls back to Ollama Cloud (`OLLAMA_CLOUD_API_KEY`, `OLLAMA_CLOUD_MODEL` in `backend/config.py`).
  - `llama-server` can also run server-side next to the Docker stack, with the same GGUF files and API as the research setup.
  - Decide this before removing the cloud fallback, so production keeps a working embedder.
  - *2026-10-21: the Ollama Cloud fallback was removed; the app embeds with local Ollama only. Moving off Ollama is still open.*
- **2026-10-11 — Keep `src.similarity` names stable.** The backend imports `MODEL_MAP`, `OLLAMA_MODEL_MAP` and `MAX_TEXT_CHARS` from `research/src/similarity.py`. The research refactor keeps these names, but the coupling is fragile.
  - Give the backend its own model config, or a small shared module.
- **2026-10-11 — Qwen3-Embedding pooling and dimension.** The backend expects 4096-dim vectors, i.e. the 8B model.
  - Whatever runtime replaces Ollama must use the model's intended pooling (last token for Qwen3-Embedding).
  - All stored pgvector embeddings must be regenerated with the same runtime and quantization; vectors from different runtimes are not comparable.

## Stage-2 LLM reranking (`backend/services/matching.py`)

- **2026-10-11 — Re-check stage 2 against the v2 results.** The case for the deployed two-stage design (Qwen3 → Llama 3.2 3B) came from v1, which the audit found invalid (F1–F6). The v2 benchmark will show whether LLM reranking helps at all once the leaks are removed. If it doesn't, simplify stage 2 or replace it, e.g. with a cross-encoder such as bge-reranker. *(Answered in the entries below: listwise and pointwise Llama do not help; bge-reranker-base scored below BM25 and TF-IDF in v2; Qwen3-Reranker-4B helps modestly.)*
- **2026-10-12 — v2 answer on stage 2.** On the leak-free v2 benchmark (`research/audit/BEFORE_AFTER.md`):
  - **Reranking lowers the ranking.** Reranking Qwen3's top 10 with listwise Llama 3.2 3B scores 13.0 / 10.4 R-precision points **below** Qwen3 alone. Stage-1 recall is not the cause: the top 10 already holds about 90% of the true references.
  - **Pointwise is the only competitive LLM variant.** It scores above BM25, TF-IDF and bge-reranker, but still below every embedding model.
  - **MiniLM (22M) is within 3.7 / 4.3 R-precision points of Qwen3-Embedding-8B.**
  - **Implications for the app.**
    - The deployed stage 2 (`_llm_generate`) scores each researcher separately, so it is pointwise, not listwise.
    - v2 did not test pointwise reranking on top of Qwen3. Pointwise on its own scores below Qwen3 (78.8 vs 87.0), so stage 2 needs its own benchmark before anyone can claim it helps; keep or drop it based on that. *(Phase 5 has since tested it: see 2026-10-13.)*
    - A smaller embedding model is a reasonable cost trade-off.
- **2026-10-11 — Position bias in the app.** The audit of v1 (F1, F2) found that Llama 3.2 3B is sensitive to candidate order and to the format example in the prompt.
  - `_llm_generate` scores researchers one at a time, so it's pointwise and order effects are smaller. Still, audit its prompt for leading examples.
  - Log how often LLM output fails to parse, and what the code does then.
- **2026-10-11 — Failure handling.** When the LLM call fails, record it explicitly instead of silently using the embedding order. v1's fallback quietly favored a fixed order.
- **2026-10-13 — Phase 5 evidence on a pointwise stage 2** (`research/v2/11_end_to_end.ipynb`). Pointwise Llama 3.2 3B was used to rerank Qwen3-Embedding's top 100 over a 11,967-paper corpus (118 test queries).
  - Used alone, it lowers nDCG@10 from 0.340 to 0.175.
  - Fused with the embedding score (weight chosen on dev), it changes nothing measurable (−0.004, n.s.).
  - Within a list, it separates cited from other papers worse than the embedding (AUC 0.66 vs 0.76).
  - The task (paper → cited paper) and prompt differ from the app's (paper → researcher, with the researcher's top-5 matching papers), so this is evidence, not a test of the app. The direct test is Phase 6B. Until then, the stage-2 LLM call is a cost with no demonstrated benefit.
- **2026-10-14 — A trained reranker as a stage-2 option** (`research/v2/12_qwen3_reranker.ipynb`). Qwen3-Reranker-4B (local, about 8 GB in fp16), fused with the embedding score at α = 0.8 chosen on dev, beats the embedding alone on the same 118 queries.
  - R-precision: +3.2 points (Holm p = 0.040).
  - nDCG@10: +0.021 (not significant after Holm).
  - Within-list AUC: 0.82, against 0.76 for the embedding.
  - Cost on an M1 Max: 0.46–0.86 s per pair (memory-dependent), against about 0.2–0.35 s for Llama 3.2 3B. Worth testing as the app's stage 2 in Phase 6B.

## Ideas

- Test Qwen3-Reranker-4B, fused with the embedding score, as the app's stage 2 (Phase 6B). It is the only second stage the benchmark found helpful; pointwise Llama and bge-reranker-base were not.
- The co-citation graph-expansion work (Phase 5) added no significant recall on top of a strong embedding first stage, so it is not a priority for the app's candidate generation.

## BOUN seed data (2026-10-15)

- **`boun.csv` has known problems** (`research/audit/BOUN_DATA.md`). It keeps records OpenAlex now types as errata, editorials and similar non-research works; it misses conference papers, preprints and book chapters; and its author lists stop at 100, so BOUN members of large collaborations beyond the first 100 authors are missing (223 records are cut).
- **A cleaned replacement exists** in `research/data/boun/` (7,822 works, 3,648 BOUN author ids, duplicates merged, earliest version date kept, misattributed collaboration authors removed). Switching the seeder to it is a separate app change; the stage-1 field ablation on the new data should come first.
- **Profiles of collaboration physicists:** 311 researchers have only 100+-author works, so their profile is collaboration papers alone. Worth deciding whether such works should count fully in a profile.
- **OpenAlex affiliation errors.** On 6 ATLAS/BESIII papers OpenAlex marks 77–370 authors as BOUN; 991 people were BOUN only through these. The cleaned data drops them. None of the 6 works is in `boun.csv`, so the app's current researcher list is not affected; a seeder that reads full author lists must apply the same check.
- **Abstracts from Crossref / Semantic Scholar** (591 works) are not in the repository (copyright, public repo). The app would need its own lookup, or must embed those works from title and topics only.
