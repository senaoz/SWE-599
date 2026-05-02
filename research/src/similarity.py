import hashlib
import json
import os
import time

import numpy as np
import requests
import torch
import google.generativeai as genai
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------------------
# Device & model config
# ---------------------------------------------------------------------------

DEVICE = 'mps' if torch.backends.mps.is_available() else ('cuda' if torch.cuda.is_available() else 'cpu')

# Max character lengths per model (~1 token ≈ 4 chars)
MAX_TEXT_CHARS = {
    'all-MiniLM-L6-v2':          1024,
    'allenai/specter2_base':      2048,
}

# GPU-friendly batch sizes per model
BATCH_SIZES = {
    'all-MiniLM-L6-v2':          256,
    'allenai/specter2_base':      128,
}

MODEL_MAP = {
    'minilm':   'all-MiniLM-L6-v2',
    'specter2': 'allenai/specter2_base',
}

OLLAMA_MODEL_MAP = {
    'qwen': 'qwen3-embedding:latest',
    'nomic': 'nomic-embed-text:v1.5',
    'embeddinggemma': 'embeddinggemma',
}

_MODEL_CACHE: dict = {}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _corpus_hash(texts):
    """Short MD5 hash of the first 5 texts — distinguishes different corpora."""
    return hashlib.md5(''.join(texts[:5]).encode()).hexdigest()[:8]


def _cache_path(model_name, prefix, n_texts, corpus_hash, cache_dir='data/embeddings_cache'):
    """Return the .npy cache file path for a given model + corpus combination."""
    safe = model_name.replace('/', '_').replace('-', '_')
    return os.path.join(cache_dir, f'{safe}_{prefix}_{n_texts}_{corpus_hash}.npy')


def _get_model(model_name):
    """Load a SentenceTransformer model, caching it for reuse."""
    if model_name not in _MODEL_CACHE:
        _MODEL_CACHE[model_name] = SentenceTransformer(
            model_name, trust_remote_code=True, device=DEVICE
        )
    return _MODEL_CACHE[model_name]


def _truncate_texts(texts, model_name):
    """Truncate texts to the token-safe character limit for the given model."""
    limit = MAX_TEXT_CHARS.get(model_name, 2048)
    return [t[:limit] for t in texts]


# ---------------------------------------------------------------------------
# Similarity functions
# ---------------------------------------------------------------------------

def _as_str(x):
    """Coerce corpus/query entries to str; pandas NaN / missing -> ''."""
    if x is None:
        return ''
    if isinstance(x, float) and np.isnan(x):
        return ''
    if isinstance(x, str):
        return x
    return str(x)


def bm25_similarity(query_texts, corpus_texts):
    """Compute BM25 scores between query and corpus texts.

    Returns
    -------
    np.ndarray of shape (len(query_texts), len(corpus_texts)),
    scores normalized to [0, 1] via saturation normalization.
    """
    corpus_texts = [_as_str(d) for d in corpus_texts]
    query_texts = [_as_str(q) for q in query_texts]
    tokenized_corpus = [doc.lower().split() for doc in corpus_texts]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = np.array([bm25.get_scores(q.lower().split()) for q in query_texts])
    positive = scores[scores > 0]
    k = float(np.median(positive)) if len(positive) > 0 else 1.0
    scores = np.where(scores > 0, scores / (scores + k), 0.0)
    return scores


def tfidf_similarity(query_texts, corpus_texts):
    """Compute TF-IDF cosine similarity between query and corpus texts.

    Returns
    -------
    np.ndarray of shape (len(query_texts), len(corpus_texts))
    """
    corpus_texts = [_as_str(d) for d in corpus_texts]
    query_texts = [_as_str(q) for q in query_texts]
    vectorizer = TfidfVectorizer(max_features=50000, stop_words='english')
    all_texts = list(corpus_texts) + list(query_texts)
    tfidf_matrix = vectorizer.fit_transform(all_texts)
    corpus_vectors = tfidf_matrix[:len(corpus_texts)]
    query_vectors = tfidf_matrix[len(corpus_texts):]
    return cosine_similarity(query_vectors, corpus_vectors)


def sentence_embedding_similarity(
    query_texts,
    corpus_texts,
    model_name='all-MiniLM-L6-v2',
    cache_dir='data/embeddings_cache',
    show_progress_bar=False,
):
    """Compute cosine similarity using SentenceTransformer embeddings.

    Both corpus and query embeddings are cached to disk for reuse.

    Parameters
    ----------
    query_texts : list of str
    corpus_texts : list of str
    model_name : str
    cache_dir : str
        Directory for .npy embedding caches. Pass a subdirectory (e.g.
        'data/embeddings_cache/week3') to keep separate caches per experiment.
    show_progress_bar : bool

    Returns
    -------
    np.ndarray of shape (len(query_texts), len(corpus_texts))
    """
    os.makedirs(cache_dir, exist_ok=True)
    model = _get_model(model_name)
    batch_size = BATCH_SIZES.get(model_name, 64)

    corpus_enc = _truncate_texts([_as_str(t) for t in corpus_texts], model_name)
    c_hash = _corpus_hash(corpus_enc)
    corpus_cache = _cache_path(model_name, 'corpus', len(corpus_enc), c_hash, cache_dir)

    if os.path.exists(corpus_cache):
        corpus_emb = np.load(corpus_cache)
    else:
        corpus_emb = model.encode(
            corpus_enc, batch_size=batch_size,
            show_progress_bar=show_progress_bar, convert_to_numpy=True
        )
        np.save(corpus_cache, corpus_emb)

    query_enc = _truncate_texts([_as_str(t) for t in query_texts], model_name)
    q_hash = _corpus_hash(query_enc)
    query_cache = _cache_path(model_name, 'query', len(query_enc), q_hash, cache_dir)

    if os.path.exists(query_cache):
        query_emb = np.load(query_cache)
    else:
        query_emb = model.encode(
            query_enc, batch_size=batch_size,
            show_progress_bar=show_progress_bar, convert_to_numpy=True
        )
        np.save(query_cache, query_emb)

    return cosine_similarity(query_emb, corpus_emb)


def gemini_rank_candidates(query_text, candidates, model_name='gemini-2.5-flash-lite',
                           abstract_sentences=5):
    """Rank candidate papers against a query paper in a single Gemini API call.

    Instead of one call per candidate, sends all candidates in one prompt and
    asks Gemini to return a ranked list — much cheaper and allows relative
    comparison across candidates.

    Parameters
    ----------
    query_text : str
        Text of the main (query) paper.
    candidates : list of str
        Texts of the candidate papers (18–42 items typical).
    model_name : str
    abstract_sentences : int
        Number of sentences to keep from each candidate text. Default: 3.
        Set to None to use the full text.

    Returns
    -------
    list of (candidate_idx, score)
        Sorted by score descending. Score is (N - rank) / N, where N is the
        number of candidates, so rank-1 gets score 1.0 and rank-N gets ~0.
        Falls back to original order on parse failure.
    """
    query_text = _as_str(query_text)
    n = len(candidates)

    candidate_lines = '\n'.join(f'{i + 1}. {_as_str(c)}' for i, c in enumerate(candidates))
    prompt = (
        'You are a research paper relevance ranker.\n\n'
        f'Main Paper:\n{query_text[:800]}\n\n'
        f'Candidate Papers (1–{n}):\n{candidate_lines}\n\n'
        f'Rank these {n} candidates from most to least relevant to the Main Paper. '
        'Respond ONLY with a JSON array of candidate numbers, e.g.: [3, 1, 7, ...]'
    )
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        print(response.text)
        text = response.text.strip()
        # Extract the JSON array from the response
        start, end = text.find('['), text.rfind(']')
        ranked_nums = json.loads(text[start:end + 1])
        # Convert 1-based numbers to 0-based indices with positional scores
        seen = set()
        result = []
        for rank, num in enumerate(ranked_nums):
            idx = int(num) - 1
            if 0 <= idx < n and idx not in seen:
                seen.add(idx)
                result.append((idx, (n - rank) / n))
        # Append any missing candidates at the bottom
        for idx in range(n):
            if idx not in seen:
                result.append((idx, 0.0))
        return result
    except Exception as e:
        print(f'  Gemini rank error: {e}')
        return [(i, 0.0) for i in range(n)]


def ollama_rank_candidates(query_text, candidates, model_name='llama3.2:3b',
                           ollama_url='http://localhost:11434', abstract_sentences=5):
    """Rank candidate papers against a query paper using a local Ollama model.

    Sends all candidates in one prompt and asks the model to return a ranked
    list — mirrors the gemini_rank_candidates interface.

    Parameters
    ----------
    query_text : str
    candidates : list of str
    model_name : str
        Ollama model tag, e.g. 'llama3.2:3b'.
    ollama_url : str
        Base URL of the running Ollama server.
    abstract_sentences : int
        Number of sentences to keep from each candidate. Default: 5.

    Returns
    -------
    list of (candidate_idx, score)
        Sorted by score descending. Score is (N - rank) / N.
        Falls back to original order on parse failure.
    """
    query_text = _as_str(query_text)
    n = len(candidates)

    def _truncate_sentences(text, k):
        sents = text.split('. ')
        return '. '.join(sents[:k]) if k and len(sents) > k else text

    candidate_lines = '\n'.join(
        f'{i + 1}. {_truncate_sentences(_as_str(c), abstract_sentences)}'
        for i, c in enumerate(candidates)
    )
    prompt = (
        'You are a research paper relevance ranker.\n\n'
        f'Main Paper:\n{query_text[:800]}\n\n'
        f'Candidate Papers (1\u2013{n}):\n{candidate_lines}\n\n'
        f'Rank these {n} candidates from most to least relevant to the Main Paper. '
        'Respond ONLY with a JSON array of candidate numbers, e.g.: [3, 1, 7, ...]'
    )
    try:
        resp = requests.post(
            f'{ollama_url}/api/chat',
            headers={'Origin': ollama_url},
            json={
                'model': model_name,
                'messages': [{'role': 'user', 'content': prompt}],
                'stream': False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        text = resp.json()['message']['content'].strip()
        start, end = text.find('['), text.rfind(']')
        ranked_nums = json.loads(text[start:end + 1])
        seen = set()
        result = []
        for rank, num in enumerate(ranked_nums):
            idx = int(num) - 1
            if 0 <= idx < n and idx not in seen:
                seen.add(idx)
                result.append((idx, (n - rank) / n))
        for idx in range(n):
            if idx not in seen:
                result.append((idx, 0.0))
        return result
    except Exception as e:
        print(f'  Ollama rank error: {e}')
        return [(i, 0.0) for i in range(n)]


def ollama_embedding_similarity(
    query_texts,
    corpus_texts,
    model_name='qwen3-embedding:latest',
    ollama_url='http://localhost:11434',
    cache_dir='data/embeddings_cache',
):
    """Compute cosine similarity using Ollama embedding models (e.g. qwen3-embedding).

    Calls /api/embed in batches and caches results to disk.

    Parameters
    ----------
    query_texts : list of str
    corpus_texts : list of str
    model_name : str
        Ollama model tag, e.g. 'qwen3-embedding:latest'.
    ollama_url : str
    cache_dir : str

    Returns
    -------
    np.ndarray of shape (len(query_texts), len(corpus_texts))
    """
    os.makedirs(cache_dir, exist_ok=True)

    def _embed(texts, prefix):
        safe = model_name.replace('/', '_').replace('-', '_').replace(':', '_')
        h = _corpus_hash([_as_str(t) for t in texts])
        cache_file = os.path.join(cache_dir, f'{safe}_{prefix}_{len(texts)}_{h}.npy')
        if os.path.exists(cache_file):
            return np.load(cache_file)
        resp = requests.post(
            f'{ollama_url}/api/embed',
            json={'model': model_name, 'input': [_as_str(t) for t in texts]},
            timeout=300,
        )
        resp.raise_for_status()
        emb = np.array(resp.json()['embeddings'], dtype=np.float32)
        np.save(cache_file, emb)
        return emb

    corpus_emb = _embed(corpus_texts, 'corpus')
    query_emb = _embed(query_texts, 'query')
    return cosine_similarity(query_emb, corpus_emb)


def combined_embedding_similarity(
    query_texts,
    corpus_texts,
    st_model_name='all-MiniLM-L6-v2',
    ollama_model='qwen3-embedding:latest',
    ollama_url='http://localhost:11434',
    cache_dir='data/embeddings_cache',
):
    """Cosine similarity on L2-normalised SentenceTransformer + Ollama embedding vectors concatenated.

    Both sources are L2-normalised before concatenation so neither dominates
    by magnitude. Suitable only when the Ollama model is a dedicated embedding
    model (e.g. qwen3-embedding:latest), not a generative chat model.

    Returns
    -------
    np.ndarray of shape (len(query_texts), len(corpus_texts))
    """
    os.makedirs(cache_dir, exist_ok=True)

    # ── SentenceTransformer embeddings ────────────────────────────────────
    st_model = _get_model(st_model_name)
    batch_size = BATCH_SIZES.get(st_model_name, 64)

    corpus_enc = _truncate_texts([_as_str(t) for t in corpus_texts], st_model_name)
    c_hash = _corpus_hash(corpus_enc)
    corpus_cache_st = _cache_path(st_model_name, 'corpus', len(corpus_enc), c_hash, cache_dir)
    if os.path.exists(corpus_cache_st):
        corpus_emb_st = np.load(corpus_cache_st)
    else:
        corpus_emb_st = st_model.encode(corpus_enc, batch_size=batch_size, convert_to_numpy=True)
        np.save(corpus_cache_st, corpus_emb_st)

    query_enc = _truncate_texts([_as_str(t) for t in query_texts], st_model_name)
    q_hash = _corpus_hash(query_enc)
    query_cache_st = _cache_path(st_model_name, 'query', len(query_enc), q_hash, cache_dir)
    if os.path.exists(query_cache_st):
        query_emb_st = np.load(query_cache_st)
    else:
        query_emb_st = st_model.encode(query_enc, batch_size=batch_size, convert_to_numpy=True)
        np.save(query_cache_st, query_emb_st)

    # ── Ollama embeddings (reuses ollama_embedding_similarity cache) ──────
    def _embed_ollama(texts, prefix):
        safe = ollama_model.replace('/', '_').replace('-', '_').replace(':', '_')
        h = _corpus_hash([_as_str(t) for t in texts])
        cache_file = os.path.join(cache_dir, f'{safe}_{prefix}_{len(texts)}_{h}.npy')
        if os.path.exists(cache_file):
            return np.load(cache_file)
        resp = requests.post(
            f'{ollama_url}/api/embed',
            json={'model': ollama_model, 'input': [_as_str(t) for t in texts]},
            timeout=300,
        )
        resp.raise_for_status()
        emb = np.array(resp.json()['embeddings'], dtype=np.float32)
        np.save(cache_file, emb)
        return emb

    corpus_emb_ol = _embed_ollama(corpus_texts, 'corpus')
    query_emb_ol = _embed_ollama(query_texts, 'query')

    # ── L2-normalise then concatenate ─────────────────────────────────────
    def _l2_norm(x):
        norms = np.linalg.norm(x, axis=1, keepdims=True)
        return x / np.where(norms == 0, 1.0, norms)

    corpus_emb = np.concatenate([_l2_norm(corpus_emb_st), _l2_norm(corpus_emb_ol)], axis=1)
    query_emb = np.concatenate([_l2_norm(query_emb_st), _l2_norm(query_emb_ol)], axis=1)

    return cosine_similarity(query_emb.astype(np.float32), corpus_emb.astype(np.float32))


def gemini_score_pair(query_text, candidate_text, model_name='gemini-2.5-flash-lite'):
    """Use Gemini to score semantic similarity between two papers (returns 0–1).
    Returns 0.0 on API error rather than None, so callers need no None-check.
    """
    query_text = _as_str(query_text)
    candidate_text = _as_str(candidate_text)
    prompt = (
        'Rate the semantic similarity between these two academic paper descriptions '
        'on a scale of 0 to 100, where 0 is completely unrelated and 100 is identical.\n\n'
        f'Paper 1:\n{query_text[:800]}\n\nPaper 2:\n{candidate_text[:800]}\n\n'
        'Respond with only a single integer.'
    )
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        score = int(''.join(filter(str.isdigit, response.text.strip()))[:3])
        return min(max(score, 0), 100) / 100.0
    except Exception as e:
        print(f'  Gemini error: {e}')
        return 0.0
