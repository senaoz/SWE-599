# SWE-599 — BOUN Paper Recommender

Automated paper recommendation system for Boğaziçi University (BOUN) researchers. Users follow academic institutions; when new papers are published, the system matches them against BOUN researcher profiles using a 2-stage pipeline (Qwen3 embeddings + Llama 3.2 3B reranking).

> The research in this repository finds that the Llama stage 2 does not improve on Qwen3-Embedding alone. A redesign without it is drafted in [`docs/MATCHING_DESIGN.md`](docs/MATCHING_DESIGN.md); known issues are in [`APP_NOTES.md`](APP_NOTES.md).

---

## How to Run

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- [Ollama](https://ollama.com/) — must be running on the host machine
- Pull the required models:

```bash
ollama pull qwen3-embedding        # Stage 1 embedding model (4096-d)
ollama pull llama3.2:3b             # reranking model (~2 GB)
```

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
OLLAMA_CLOUD_API_KEY=...         # embedding fallback when local Ollama is unreachable
```

### 2. Start the Stack

```bash
docker-compose up --build
```

This starts:
- **PostgreSQL** on port `5432`
- **Backend** (FastAPI) on port `8001`

On first start, the backend automatically:
1. Creates database tables
2. Seeds 2671 BOUN researchers from `research/data/cleaned/boun.csv`
3. Computes embeddings for ~7,800 researcher–paper rows (4,608 papers) in the background

Wait until you see this in the logs before using the app:

```
INFO:backend.services.seeder:Profile embeddings and individual paper embeddings stored.
```

### 3. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173**

### 4. First Use

1. Open http://localhost:5173 and register an account
2. Go to **Institutions** → follow one or more institutions (a fixed list: MIT, Stanford, Harvard, UC Berkeley, U. Michigan, Google, Google DeepMind)
3. Go to **Admin** → click **Run matching job now** (the scheduled job first runs 6 hours after start-up; **Rematch unmatched** reruns both stages for papers with no match)
4. Go to **Dashboard** → see papers matched to BOUN researchers
5. Go to **Researchers** → browse/search all 2671 BOUN researchers
6. Mark a listed researcher as relevant or not (thumbs-up/down); feedback is stored but not yet used for matching

The Admin page is open to every logged-in user (no role check).

### Production

`docker-compose.prod.yml` runs the whole stack in containers: PostgreSQL, the backend, Ollama, a one-off `ollama-init` service that pulls `qwen3-embedding` and `llama3.2:3b`, and the frontend built into nginx (which proxies `/api/` to the backend). Set `DB_PASSWORD`, `JWT_SECRET` and `VITE_API_URL` in `.env` (see `.env.example`), then:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The file publishes no host ports; expose the frontend's port 80 through a reverse proxy or a `ports:` entry. For an NVIDIA GPU, uncomment the `deploy` block of the `ollama` service.

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
                    │  PostgreSQL (:5432)                       │
                    │  researchers, researcher_papers,          │
                    │  fetched_papers, paper_researcher_matches,│
                    │  paper_feedback                           │
                    └────────────────┬─────────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────────┐
                    │  Ollama (host:11434)                      │
                    │  (Ollama Cloud: embedding fallback)       │
                    │  qwen3-embedding — Stage 1 embeddings     │
                    │  llama3.2:3b     — Stage 2 reranking      │
                    └──────────────────────────────────────────┘
```

### Matching Pipeline (2-Stage RAG)

Every 6 hours (or on manual trigger):

1. **Fetch** — new papers from followed institutions via the OpenAlex API, from each institution's last fetched publication date (the first run starts from today), at most 200 per institution per run
2. **Stage 1 — Retrieve** — embed new papers with Qwen3-Embedding (local Ollama, Ollama Cloud as fallback); cosine similarity against the ~7,800 researcher–paper embeddings, computed in Python; drop pairs below `MATCH_THRESHOLD`; group by researcher → top-10 by max score
3. **Stage 2 — Rerank** — top-10 researchers sent to Llama 3.2 3B one at a time (pointwise) with context (new paper + the researcher's top-5 matching BOUN papers); Llama returns `RELEVANT <score>` or `IRRELEVANT <score>`. The LLM score replaces the cosine score; `IRRELEVANT` or a reply that does not start with `RELEVANT` drops the researcher; if the LLM call fails, the cosine score is kept. Research evidence on this stage: [`APP_NOTES.md`](APP_NOTES.md)
4. **Store** — `PaperResearcherMatch` rows with score ≥ `MATCH_THRESHOLD`, matched paper IDs, and LLM score

The feed shows at most `TOP_K_MATCHES` researchers per paper, with score ≥ 0.3.

---

## Project Structure

```
├── backend/
│   ├── routers/          # auth, institutions, papers, researchers, feedback, admin
│   ├── services/
│   │   ├── matching.py   # 2-stage RAG matching job
│   │   ├── seeder.py     # BOUN researcher seeding + embedding computation
│   │   ├── embedding.py  # encode_texts_ollama, cosine similarity
│   │   └── openalex.py   # paper/institution fetching via OpenAlex API
│   ├── scheduler.py      # APScheduler job every JOB_INTERVAL_HOURS
│   ├── models.py         # SQLAlchemy ORM models
│   ├── config.py         # constants and thresholds
│   └── main.py           # FastAPI app + lifespan (init DB, seed, scheduler)
├── frontend/
│   └── src/pages/        # Dashboard, Institutions, Researchers, ResearcherDetail, Admin, Login, Register
├── research/
│   ├── src/              # shared library (also imported by backend/)
│   ├── data/cleaned/     # boun.csv (BOUN papers for the app)
│   ├── data/boun/        # cleaned BOUN works, not used by the app yet (research/audit/BOUN_DATA.md)
│   ├── v1/               # numbered notebooks + benchmark results
│   └── v2/               # leak-free benchmark, Phase 5, gold standard (see research/README.md)
├── docs/MATCHING_DESIGN.md  # draft redesign of the matching
├── docker-compose.yml       # dev: db + backend (Ollama and frontend on the host)
└── docker-compose.prod.yml  # prod: db, backend, Ollama, frontend (nginx)
```

---

## Configuration

Key constants in `backend/config.py` (all but `RETRIEVE_MODEL` can be overridden by an environment variable of the same name):

| Variable | Default | Description |
|---|---|---|
| `MATCH_THRESHOLD` | `0.3` | Min cosine for a BOUN paper to count, and min score to store a match |
| `TOP_K_MATCHES` | `5` | Researchers shown per paper in UI |
| `RETRIEVE_MODEL` | `qwen` | Stage 1 embedding model (qwen3-embedding via Ollama) |
| `RAG_RETRIEVE_TOP_K` | `10` | Researchers selected in Stage 1 |
| `RAG_LLM_TOP_K` | `10` | Researchers sent to Llama in Stage 2 |
| `RAG_CONTEXT_PAPERS` | `5` | BOUN papers per researcher in the Stage 2 prompt |
| `LLM_GENERATE_MODEL` | `llama3.2:3b` | Stage 2 Ollama model |
| `OLLAMA_URL` | `http://localhost:11434` | Local Ollama |
| `OLLAMA_CLOUD_API_KEY`, `OLLAMA_CLOUD_MODEL` | unset, `qwen3:embedding` | Embedding fallback |
| `OPENALEX_EMAIL` | unset | OpenAlex polite pool |
| `JWT_EXPIRE_MINUTES` | `10080` | Login lifetime (7 days) |
| `JOB_INTERVAL_HOURS` | `6` | Background job frequency |

---

## Research

The research (v1 audit, v2, Phase 5 and the human-labelled gold standard) is documented in [`research/README.md`](research/README.md) and summarized in the main [`README.md`](README.md). The v1 numbers once listed here are superseded; see [`research/audit/AUDIT.md`](research/audit/AUDIT.md).
