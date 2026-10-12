# App backlog and ideas

A running log of changes the deployed recommender (`backend/`, `frontend/`) needs, collected while doing the v2 research audit (`research/audit/AUDIT.md`). Research work does not touch the app; these items are for a later, combined update.

Each entry gives the date it was noted, what to do, and why.

## Model serving

- **2026-10-11 — Move off Ollama and drop the cloud fallback.** The research side now serves models through Jan's local OpenAI-compatible API (`/v1/chat/completions`, `/v1/embeddings`). The backend still calls Ollama (`backend/services/embedding.py`) and falls back to Ollama Cloud (`OLLAMA_CLOUD_API_KEY`, `OLLAMA_CLOUD_MODEL` in `backend/config.py`).
  - Jan is a desktop app and can't run inside the Docker container. The backend needs a server-side local runtime instead: `llama-server` from llama.cpp, which serves the same GGUF files Jan uses through the same OpenAI-style API.
  - Decide this before removing the cloud fallback, so production keeps a working embedder.
- **2026-10-11 — Keep `src.similarity` names stable.** The backend imports `MODEL_MAP`, `OLLAMA_MODEL_MAP` and `MAX_TEXT_CHARS` from `research/src/similarity.py`. The research refactor keeps these names, but the coupling is fragile.
  - Give the backend its own model config, or a small shared module.
- **2026-10-11 — Qwen3-Embedding pooling and dimension.** The backend expects 4096-dim vectors, i.e. the 8B model.
  - Whatever runtime replaces Ollama must use the model's intended pooling (last token for Qwen3-Embedding).
  - All stored pgvector embeddings must be regenerated with the same runtime and quantization; vectors from different runtimes are not comparable.

## Stage-2 LLM reranking (`backend/services/matching.py`)

- **2026-10-11 — Re-check stage 2 against the v2 results.** The case for the deployed two-stage design (Qwen3 → Llama 3.2 3B) came from v1, which the audit found invalid (F1–F6). The v2 benchmark will show whether LLM reranking helps at all once the leaks are removed. If it doesn't, simplify stage 2 or replace it, e.g. with a cross-encoder such as bge-reranker.
- **2026-10-12 — v2 answer on stage 2.** On the leak-free v2 benchmark (`research/audit/BEFORE_AFTER.md`):
  - **Reranking lowers the ranking.** Reranking Qwen3's top 10 with listwise Llama 3.2 3B scores 13.0 / 10.4 R-precision points **below** Qwen3 alone. Stage-1 recall is not the cause: the top 10 already holds about 90% of the true references.
  - **Pointwise is the only competitive LLM variant.** It scores above BM25, TF-IDF and bge-reranker, but still below every embedding model.
  - **MiniLM (22M) is within 4 points of Qwen3-Embedding-8B.**
  - **Implications for the app.**
    - The deployed stage 2 (`_llm_generate`) scores each researcher separately, so it is pointwise, not listwise.
    - v2 did not test pointwise reranking on top of Qwen3. Pointwise on its own scores below Qwen3 (78.8 vs 87.0), so stage 2 needs its own benchmark before anyone can claim it helps; keep or drop it based on that.
    - A smaller embedding model is a reasonable cost trade-off.
- **2026-10-11 — Position bias in the app.** v1 found that Llama 3.2 3B is sensitive to candidate order and to the format example in the prompt.
  - `_llm_generate` scores researchers one at a time, so it's pointwise and order effects are smaller. Still, audit its prompt for leading examples.
  - Log how often LLM output fails to parse, and what the code does then.
- **2026-10-11 — Failure handling.** When the LLM call fails, record it explicitly instead of silently using the embedding order. v1's fallback quietly favored a fixed order.

## Ideas

- Offer the v2 pointwise and cross-encoder scorers as cheaper stage-2 options once the benchmark ranks them.
- The research co-citation / graph-expansion work (audit Phase 4) could later feed the app's candidate generation.
