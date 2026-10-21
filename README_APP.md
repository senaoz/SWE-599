# SWE-599 — BOUN Paper Recommender

Automated paper recommendation system for Boğaziçi University (BOUN) researchers. Users follow academic institutions; when new papers are published, the system matches them against BOUN researcher profiles by cosine similarity of Qwen3-Embedding vectors.

> The research in this repository found that an LLM reranking stage does not improve on Qwen3-Embedding alone, on citation labels or on human expertise labels, so the app has no second stage. The planned redesign and its decisions are in [`docs/MATCHING_DESIGN.md`](docs/MATCHING_DESIGN.md); known issues are in [`APP_NOTES.md`](APP_NOTES.md).

---

## How to Run

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- [Ollama](https://ollama.com/) — must be running on the host machine
- Pull the embedding model:

```bash
ollama pull qwen3-embedding        # embedding model (4096-d)
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

1. Open http://localhost:5173 and register an account, then make it an admin:
   ```bash
   docker compose exec backend python -m backend.make_admin you@example.com
   ```
2. Go to **Institutions** → follow one or more institutions (a fixed list: MIT, Stanford, Harvard, UC Berkeley, U. Michigan, Google, Google DeepMind)
3. Go to **Admin** → click **Run matching job now** (the scheduled job first runs 6 hours after start-up; **Rematch unmatched** reruns matching for papers with no match)
4. Go to **Dashboard** → see papers matched to BOUN researchers
5. Go to **Researchers** → browse/search all 2671 BOUN researchers
6. Mark a listed researcher as relevant or not (thumbs-up/down); feedback is stored but not yet used for matching

Only admins see the Admin page; the `/admin` API returns 403 for everyone else. Admin rights live in `users.is_admin` and are granted or revoked (`--revoke`) with `backend.make_admin`.

### Production

`docker-compose.prod.yml` runs the whole stack in containers: PostgreSQL, the backend, Ollama, a one-off `ollama-init` service that pulls `qwen3-embedding`, and the frontend built into nginx (which proxies `/api/` to the backend). Set `DB_PASSWORD`, `JWT_SECRET` and `VITE_API_URL` in `.env` (see `.env.example`), then:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

After registering, grant admin rights with `docker compose -f docker-compose.prod.yml exec backend python -m backend.make_admin you@example.com`.

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
                    │  qwen3-embedding — embeddings             │
                    └──────────────────────────────────────────┘
```

### Matching Pipeline

Every 6 hours (or on manual trigger):

1. **Fetch** — new papers from followed institutions via the OpenAlex API, from each institution's last fetched publication date (the first run starts from today), at most 200 per institution per run
2. **Embed** — new papers with Qwen3-Embedding via local Ollama (if Ollama is unreachable, the job logs the error and stops)
3. **Rank** — cosine similarity against the ~7,800 researcher–paper embeddings, computed in Python; drop pairs below `MATCH_THRESHOLD`; score each researcher by their best paper (`MATCH_AGGREGATION`); keep the top `RAG_RETRIEVE_TOP_K` researchers (`backend/services/ranking.py`, shared by the matching and rematch jobs)
4. **Store** — `PaperResearcherMatch` rows with the cosine score, the embedding model as `model`, and the researcher's top `RAG_CONTEXT_PAPERS` matching BOUN papers

The feed shows at most `TOP_K_MATCHES` researchers per paper, with score ≥ `MATCH_THRESHOLD`; the paper page shows all stored researchers.

---

## Project Structure

```
├── backend/
│   ├── routers/          # auth, institutions, papers, researchers, feedback, admin
│   ├── services/
│   │   ├── matching.py   # matching and rematch jobs
│   │   ├── ranking.py    # threshold, aggregation and top-K per paper
│   │   ├── seeder.py     # BOUN researcher seeding + embedding computation
│   │   ├── embedding.py  # encode_texts_ollama, cosine similarity
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
| `MATCH_THRESHOLD` | `0.3` | Min cosine for a BOUN paper to count; also the feed's minimum score |
| `TOP_K_MATCHES` | `5` | Researchers shown per paper in UI |
| `RETRIEVE_MODEL` | `qwen` | Embedding model (qwen3-embedding via Ollama) |
| `MATCH_AGGREGATION` | `max` | Researcher score from their papers' cosines: `max` or `mean_top3` |
| `RAG_RETRIEVE_TOP_K` | `10` | Researchers stored per paper |
| `RAG_CONTEXT_PAPERS` | `5` | Matching BOUN papers stored per researcher |
| `OLLAMA_URL` | `http://localhost:11434` | Local Ollama |
| `OPENALEX_EMAIL` | unset | OpenAlex polite pool |
| `JWT_EXPIRE_MINUTES` | `10080` | Login lifetime (7 days) |
| `JOB_INTERVAL_HOURS` | `6` | Background job frequency |

---

## Research

The research (v1 audit, v2, Phase 5 and the human-labelled gold standard) is documented in [`research/README.md`](research/README.md) and summarized in the main [`README.md`](README.md). The v1 numbers once listed here are superseded; see [`research/audit/AUDIT.md`](research/audit/AUDIT.md).
