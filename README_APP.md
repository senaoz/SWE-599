# SWE-599 — BOUN Paper Recommender

Automated paper recommendation system for Boğaziçi University (BOUN) researchers. Users follow academic institutions; when new papers are published, the system matches them against BOUN researcher profiles using a 2-stage pipeline (Qwen3 embeddings + Llama 3.2 3B reranking).

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
cp .env.example .env   # if it exists, otherwise create manually
```

Minimum required variables:

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

1. Open http://localhost:5173 and register an account
2. Go to **Institutions** → follow one or more institutions (MIT, Stanford, Harvard, etc.)
3. Go to **Admin** → click **Run matching job now**
4. Go to **Dashboard** → see papers matched to BOUN researchers
5. Go to **Researchers** → browse/search all 2671 BOUN researchers

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
                    │  /admin        — stats + job trigger      │
                    └────────────────┬─────────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────────┐
                    │  PostgreSQL (:5432)                       │
                    │  researchers, researcher_papers,          │
                    │  fetched_papers, paper_researcher_matches │
                    └────────────────┬─────────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────────┐
                    │  Ollama (host:11434)                      │
                    │  qwen3-embedding — Stage 1 embeddings     │
                    │  llama3.2:3b     — Stage 2 reranking      │
                    └──────────────────────────────────────────┘
```

### Matching Pipeline (2-Stage RAG)

Every 6 hours (or on manual trigger):

1. **Fetch** — new papers from followed institutions via OpenAlex API
2. **Stage 1 — Retrieve** — embed new papers with Qwen3-Embedding; cosine similarity against the ~7,800 researcher–paper embeddings; group by researcher → top-10 by max score
3. **Stage 2 — Rerank** — top-10 researchers sent to Llama 3.2 3B one at a time (pointwise) with context (new paper + the researcher's top-5 matching BOUN papers); Llama returns `RELEVANT <score>` or `IRRELEVANT <score>`; the LLM score is the final score. Research evidence on this stage: [`APP_NOTES.md`](APP_NOTES.md)
4. **Store** — `PaperResearcherMatch` rows with score, matched paper IDs, and LLM score

---

## Project Structure

```
├── backend/
│   ├── routers/          # auth, institutions, papers, researchers, admin
│   ├── services/
│   │   ├── matching.py   # 2-stage RAG matching job
│   │   ├── seeder.py     # BOUN researcher seeding + embedding computation
│   │   ├── embedding.py  # encode_texts_ollama, cosine similarity
│   │   └── openalex.py   # paper/institution fetching via OpenAlex API
│   ├── models.py         # SQLAlchemy ORM models
│   ├── config.py         # constants and thresholds
│   └── main.py           # FastAPI app + lifespan (init DB, seed, scheduler)
├── frontend/
│   └── src/pages/        # Dashboard, Institutions, Researchers, Admin
├── research/
│   ├── src/              # shared library (also imported by backend/)
│   ├── data/cleaned/     # boun.csv (BOUN papers for the app)
│   ├── v1/               # numbered notebooks + benchmark results
│   └── v2/               # leak-free benchmark and Phase 5 (see research/README.md)
└── docker-compose.yml
```

---

## Configuration

Key constants in `backend/config.py`:

| Variable | Default | Description |
|---|---|---|
| `MATCH_THRESHOLD` | `0.3` | Min score to store a match |
| `TOP_K_MATCHES` | `5` | Researchers shown per paper in UI |
| `RETRIEVE_MODEL` | `qwen` | Stage 1 embedding model (qwen3-embedding via Ollama) |
| `RAG_RETRIEVE_TOP_K` | `10` | Researchers selected in Stage 1 |
| `RAG_LLM_TOP_K` | `10` | Researchers sent to Llama in Stage 2 |
| `RAG_CONTEXT_PAPERS` | `5` | BOUN papers per researcher in the Stage 2 prompt |
| `JOB_INTERVAL_HOURS` | `6` | Background job frequency |

---

## Research

The research benchmark (v1 audit, v2 and Phase 5) is documented in [`research/README.md`](research/README.md) and summarized in the main [`README.md`](README.md). The v1 numbers once listed here are superseded; see [`research/audit/AUDIT.md`](research/audit/AUDIT.md).
