import hashlib
import os

import numpy as np
import torch
from sentence_transformers.sentence_transformer import modules as st_models
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

# Read by backend/services/embedding.py only; research code serves these through Jan
# (see src/jan.py and APP_NOTES.md).
OLLAMA_MODEL_MAP = {
    'qwen': 'qwen3-embedding:latest',
    'nomic': 'nomic-embed-text:v1.5',
    'embeddinggemma': 'embeddinggemma',
}

# Models that ship as plain transformers checkpoints, without a sentence-transformers
# pooling config. Loading them by name would silently add mean pooling; SPECTER2 is
# trained with the [CLS] token (model card), so it is built explicitly.
POOLING_OVERRIDES = {
    'allenai/specter2_base': 'cls',
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
        if model_name in POOLING_OVERRIDES:
            word = st_models.Transformer(model_name)
            pool = st_models.Pooling(word.get_embedding_dimension(), pooling_mode=POOLING_OVERRIDES[model_name])
            model = SentenceTransformer(modules=[word, pool], device=DEVICE)
        else:
            model = SentenceTransformer(model_name, trust_remote_code=True, device=DEVICE)
        _MODEL_CACHE[model_name] = model
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
