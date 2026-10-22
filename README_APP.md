# SWE-599 — Scholar Radar

Scholar Radar is an automated paper recommendation system for Boğaziçi University (BOUN) researchers. Users follow academic institutions; when new papers are published, the system retrieves the most similar BOUN works by cosine similarity of Qwen3-Embedding vectors and lists those works' BOUN authors.

> The research in this repository found that an LLM reranking stage does not improve on Qwen3-Embedding alone, on citation labels or on human expertise labels, so the app has no second stage. The design and its decisions are in [`docs/MATCHING_DESIGN.md`](docs/MATCHING_DESIGN.md); known issues are in [`APP_NOTES.md`](APP_NOTES.md).


<img width="1030" height="798" alt="Screenshot 2026-10-22 at 08 18 36" src="https://github.com/user-attachments/assets/a69ba0dd-3e77-415b-8b01-d6668709eeff" />
<img width="1036" height="1125" alt="Screenshot 2026-10-22 at 08 18 51" src="https://github.com/user-attachments/assets/9326d338-4804-4753-9cd2-bb07e27a99bd" />


---

## How to Run

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- `llama-server` from [llama.cpp](https://github.com/ggml-org/llama.cpp) (build b11146) serving Qwen3-Embedding-8B Q4_K_M with `--pooling last` on `127.0.0.1:1337`: the research setup in [`research/README.md`](research/README.md). The backend container reaches it at `host.docker.internal:1337`.
- The cleaned BOUN data in `research/data/boun/` (Git LFS: run `git lfs pull`). Optional but much faster: the research embedding cache `research/data/v2/embeddings_boun/qwen.npz` and the Crossref/S2 abstract cache `research/data/v2/boun/` (both gitignored). With them, the 7,822 BOUN works load from the cache in about two minutes; without them, every work is embedded live (about 6 h at the speed measured locally, 2.8 s per text with another 8B model loaded; not measured on a server) and works whose abstract came from Crossref/S2 get title-only vectors.

### 1. Environment Setup

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

`.env.example` lists the production variables too. For local development the minimum is:

```env
JWT_SECRET=your-secret-key-here
```

Optional:

```env
OPENALEX_EMAIL=you@example.com   # sent to OpenAlex with each request
```

### 2. Start the Stack

```bash
docker-compose up --build
```

This starts:
- **PostgreSQL** on port `5432`
- **Backend** (FastAPI) on port `8001`

On first start, the backend automatically:
1. Creates the database tables
2. Loads 3,648 BOUN researchers, 7,822 works and their authorships from `research/data/boun/`
3. Embeds the works in the background, reusing the research cache where the text matches

Wait until you see this in the logs before running the matching job:

```
backend.services.seeder — BOUN works embedded at qwen3-emb-8b|llama.cpp-b11146-q4_k_m|d4096|last|ta_full|noinstr.
```

A database created by the old schema (with `researcher_papers`) stops start-up with an error; there is no migration, so reset it with `docker compose down -v`.

### 3. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173**

### 4. First Use

1. Open http://localhost:5173 and register an account, then make it an admin:
   ```bash
   docker compose exec backend python -m backend.make_admin you@example.com
   ```
2. Go to **Institutions** → follow one or more institutions (MIT, Stanford, Harvard, UC Berkeley, U. Michigan, Google and Google DeepMind are suggested; **Add an institution** searches all of OpenAlex by name or id)
3. Go to **Admin** → click **Run matching job now** (the scheduled job first runs 6 hours after start-up; **Rematch unmatched** reruns matching for papers with no match)
4. Go to **For me** → add your favourite Boğaziçi researchers by name (yourself included). The page then lists new papers close to their works, with the work each one was matched through.
5. Go to **Explore** → all new papers from the institutions you follow, with the Boğaziçi researchers grouped by the work they were matched through. Filter by field, date and match level.
6. Answer "Works on this topic?" (Yes / Partly / No, with an optional reason) under a paper. Answers are stored with the embedding version, score and rank that were shown; **Admin** summarizes them by rank. They are not yet used for matching.

Match levels (Strong / Likely / Weak) are bands of an uncalibrated cosine, not probabilities; the exact value is in the tooltip.

A database created before this version stops start-up with "The database schema is older than the code"; there is no migration tool yet, so reset it with `docker compose down -v`.

Only admins see the Admin page; the `/admin` API returns 403 for everyone else. Admin rights live in `users.is_admin` and are granted or revoked (`--revoke`) with `backend.make_admin`.

### Production

`docker-compose.prod.yml` runs the whole stack in containers: PostgreSQL, the backend, an `embedder` service (llama.cpp's server with Qwen3-Embedding-8B Q4_K_M, downloaded from Hugging Face on first start; it needs RAM for an 8B model, see open question O1 in the design doc), and the frontend built into nginx (which proxies `/api/` to the backend). Set `DB_PASSWORD`, `JWT_SECRET` and `VITE_API_URL` in `.env` (see `.env.example`), then:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

After registering, grant admin rights with `docker compose -f docker-compose.prod.yml exec backend python -m backend.make_admin you@example.com`.

The file publishes no host ports; expose the frontend's port 80 through a reverse proxy or a `ports:` entry. The backend mounts `./research/data`, so copy the BOUN data (and, to skip live embedding, the caches above) to the server.

---

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│  Frontend   │────▶│  FastAPI Backend (:8001)                 │
│  React/Vite │     │                                          │
│  (:5173)    │     │  /auth        — JWT register/login       │
└─────────────┘     │  /institutions — follow/unfollow         │
                    │  /papers       — paginated recommendations│
                    │  /researchers  — searchable BOUN list     │
                    │  /feedback     — thumbs-up/down per match │
                    │  /admin        — stats, job, rematch      │
                    └────────────────┬─────────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────────┐
                    │  PostgreSQL + pgvector (:5432)            │
                    │  researchers, boun_works,                 │
                    │  boun_authorships, fetched_papers,        │
                    │  paper_researcher_matches, match_evidence,│
                    │  paper_feedback                           │
                    └────────────────┬─────────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────────┐
                    │  llama-server (host:1337)                 │
                    │  Qwen3-Embedding-8B — embeddings          │
                    └──────────────────────────────────────────┘
```

### Matching Pipeline

Every 6 hours (or on manual trigger):

1. **Fetch** — new papers from followed institutions via the OpenAlex API, from each institution's cursor (following an institution starts it 14 days back), at most 200 per institution per run
2. **Embed** — `title + abstract` of each new paper with Qwen3-Embedding-8B on `llama-server`, stored with `EMBEDDING_VERSION` (if the encoder is unreachable, the job logs the error and stops)
3. **Search** — exact cosine search in PostgreSQL (pgvector `<=>`) for the `RETRIEVE_WORKS` nearest BOUN works at the current version, leaving out the paper itself (same OpenAlex id, a merged duplicate, or the same DOI)
4. **Rank** — each retrieved work counts for each of its BOUN authors; a researcher's score is their best work (`MATCH_AGGREGATION`); keep the top `RAG_RETRIEVE_TOP_K` researchers, or none if the best scores below `MATCH_THRESHOLD` (`backend/services/ranking.py`)
5. **Store** — `paper_researcher_matches` (score, rank, version) and `match_evidence` (each researcher's top `RAG_CONTEXT_PAPERS` matched works)

The feed shows at most `TOP_K_MATCHES` researchers per paper with score ≥ the dashboard's minimum score; the paper page shows all stored researchers. Only matches at the current `EMBEDDING_VERSION` are shown.

---

## Project Structure

```
├── backend/
│   ├── routers/          # auth, institutions, papers, researchers, feedback, admin
│   ├── services/
│   │   ├── matching.py   # matching and rematch jobs
│   │   ├── ranking.py    # threshold, aggregation and top-K per paper
│   │   ├── seeder.py     # loads the cleaned BOUN data, embeds works (cache first)
│   │   ├── embedding.py  # llama-server encoder, text template
│   │   └── openalex.py   # paper/institution fetching via OpenAlex API
│   ├── scheduler.py      # APScheduler job every JOB_INTERVAL_HOURS
│   ├── make_admin.py     # grant/revoke admin rights
│   ├── models.py         # SQLAlchemy ORM models
│   ├── config.py         # constants and thresholds
│   └── main.py           # FastAPI app + lifespan (init DB, seed, scheduler)
├── frontend/
│   └── src/pages/        # Dashboard, Institutions, Researchers, ResearcherDetail, Admin, Login, Register
├── research/
│   ├── src/              # shared library (also imported by backend/)
│   ├── data/boun/        # cleaned BOUN works, the app's seed (research/audit/BOUN_DATA.md)
│   ├── v1/               # numbered notebooks + benchmark results
│   └── v2/               # leak-free benchmark, Phase 5, gold standard (see research/README.md)
├── docs/MATCHING_DESIGN.md  # matching design and decisions
├── docker-compose.yml       # dev: db + backend (llama-server and frontend on the host)
└── docker-compose.prod.yml  # prod: db, backend, embedder (llama.cpp), frontend (nginx)
```

---

## Configuration

Key constants in `backend/config.py` (all but `EMBEDDING_DIM` can be overridden by an environment variable of the same name):

| Variable | Default | Description |
|---|---|---|
| `MATCH_THRESHOLD` | `0.3` | A paper whose best researcher scores below this gets no researchers; also the feed's default minimum score. Not yet calibrated |
| `TOP_K_MATCHES` | `5` | Researchers shown per paper in UI |
| `EMBED_URL` | `http://localhost:1337/v1` | OpenAI-style base URL of the encoder |
| `EMBED_MODEL` | `Qwen/Qwen3-Embedding-8B-Q4_K_M` | Model id on the encoder |
| `EMBEDDING_VERSION` | `qwen3-emb-8b\|llama.cpp-b11146-q4_k_m\|d4096\|last\|ta_full\|noinstr` | Stored with every vector and match; changing it re-embeds the BOUN works on the next start |
| `RETRIEVE_WORKS` | `50` | BOUN works retrieved per new paper |
| `RESEARCH_DIR` | `research` | Folder with `data/boun/` and the caches |
| `MATCH_AGGREGATION` | `max` | Researcher score from their works' cosines: `max` or `mean_top3` |
| `RAG_RETRIEVE_TOP_K` | `10` | Researchers stored per paper |
| `RAG_CONTEXT_PAPERS` | `5` | Matched BOUN works stored per researcher |
| `OPENALEX_EMAIL` | unset | OpenAlex polite pool |
| `JWT_EXPIRE_MINUTES` | `10080` | Login lifetime (7 days) |
| `JOB_INTERVAL_HOURS` | `6` | Background job frequency |

---

## Research

The research (v1 audit, v2, Phase 5 and the human-labelled gold standard) is documented in [`research/README.md`](research/README.md) and summarized in the main [`README.md`](README.md). The v1 numbers once listed here are superseded; see [`research/audit/AUDIT.md`](research/audit/AUDIT.md).
