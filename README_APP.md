# SWE-599 — BOUN Paper Recommender

Automated paper recommendation system for Boğaziçi University (BOUN) researchers. Users follow academic institutions; when new papers are published, the system matches them against BOUN researcher profiles using a 2-stage RAG pipeline (Qwen/nomic embeddings + Llama reranking).

---

## How to Run

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- [Ollama](https://ollama.com/) — must be running on the host machine
- Pull the required models:

```bash
ollama pull nomic-embed-text:v1.5   # embedding model (~274 MB)
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
OPENALEX_EMAIL=you@example.com   # for OpenAlex polite pool (higher rate limits)
GEMINI_API_KEY=...               # only needed for research notebooks
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
3. Computes embeddings for ~7800 papers in the background (takes ~6 minutes with nomic-embed-text)

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
                    │  nomic-embed-text — Stage 1 embeddings    │
                    │  llama3.2:3b     — Stage 2 reranking      │
                    └──────────────────────────────────────────┘
```

### Matching Pipeline (2-Stage RAG)

Every 6 hours (or on manual trigger):

1. **Fetch** — new papers from followed institutions via OpenAlex API
2. **Stage 1 — Retrieve** — embed new papers with nomic-embed-text; cosine similarity against all 7800 individual BOUN paper embeddings; group by researcher → top-20 by max score
3. **Stage 2 — Generate** — top-10 researchers sent to Llama with context (new paper + top-3 matching BOUN papers); Llama returns `RELEVANT 0.87` or `IRRELEVANT`; LLM score used as final score
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
│   ├── src/              # similarity.py, preprocessing.py, metrics.py
│   ├── data/cleaned/     # boun.csv, priority_followed.csv
│   └── eval_dataset/     # benchmark results
└── docker-compose.yml
```

---

## Configuration

Key constants in `backend/config.py`:

| Variable | Default | Description |
|---|---|---|
| `MATCH_THRESHOLD` | `0.3` | Min score to store a match |
| `TOP_K_MATCHES` | `5` | Researchers shown per paper in UI |
| `RETRIEVE_MODEL` | `nomic` | Stage 1 embedding model |
| `RAG_RETRIEVE_TOP_K` | `20` | Researchers selected in Stage 1 |
| `RAG_LLM_TOP_K` | `10` | Researchers sent to Llama in Stage 2 |
| `JOB_INTERVAL_HOURS` | `6` | Background job frequency |

---

## Research Notebooks

Offline evaluation of embedding methods (run in order):

```bash
cd research
pip install -r requirements.txt

# 1. Fetch and preprocess BOUN + followed institution papers
jupyter notebook fetch_and_preprocessing.ipynb

# 2. Compare embedding methods (TF-IDF, MiniLM, SPECTER2, Gemini, Qwen)
jupyter notebook similarity_evaluation.ipynb

# 3. Cited paper ranking benchmark (hit-rate evaluation)
jupyter notebook cited_paper_ranking.ipynb
```

Evaluated methods and hit rates (Week 3): Llama 44.99%, SPECTER2 30.21%, Gemini 42.5%, MiniLM 28.3%.
