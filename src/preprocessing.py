import ast
import html
import re
from collections import Counter

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_column(x):
    """Parse a single cell value — converts stringified dicts/lists back to Python objects."""
    if pd.isna(x):
        return None
    if isinstance(x, str):
        x = x.strip()
        if x.startswith('{') or x.startswith('['):
            try:
                return ast.literal_eval(x)
            except Exception:
                return x
    return x


def reconstruct_abstract(inv_index):
    """Reconstruct plain text from an OpenAlex abstract_inverted_index dict."""
    if not isinstance(inv_index, dict):
        return None
    words = sorted((pos, word) for word, positions in inv_index.items() for pos in positions)
    return ' '.join(w for _, w in words)


def clean_abstract(text):
    """Remove HTML entities/tags, URLs, and extra whitespace from abstract text."""
    if not isinstance(text, str):
        return None
    text = html.unescape(html.unescape(text))  # double-pass for &amp;lt; → &lt; → <
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\b(ABSTRACT|Abstract)\b', '', text)
    return text.strip()


def clean_word(word):
    """Normalize a single word: unescape HTML, strip punctuation, lowercase."""
    word = html.unescape(html.unescape(word))
    word = re.sub(r'<[^>]*>', '', word)
    word = re.sub(r'[^\w\s]', '', word)
    word = word.lower()
    return word if len(word) >= 3 else None


def extract_keywords(text, n=10):
    """Return the top-n content words from text (stopwords and short words removed)."""
    if not isinstance(text, str):
        return None
    stopwords = {
        'the', 'and', 'of', 'to', 'in', 'a', 'for', 'on', 'with', 'is', 'are',
        'this', 'that', 'these', 'those', 'from', 'using', 'used', 'based',
        'study', 'paper', 'results', 'method', 'analysis',
    }
    words = [w for w in re.findall(r'\b[a-zA-Z]+\b', text.lower())
             if w not in stopwords and len(w) > 3]
    return [w for w, _ in Counter(words).most_common(n)]


def word_freq_clean(inv_index):
    """Build a {clean_word: frequency} dict from an OpenAlex abstract_inverted_index."""
    if not isinstance(inv_index, dict):
        return None
    freq = {}
    for word, positions in inv_index.items():
        clean = clean_word(word)
        if clean:
            freq[clean] = len(positions)
    return freq


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_papers(csv_path: str, name: str) -> pd.DataFrame:
    """Load and process a raw OpenAlex papers CSV into analysis-ready format.

    Steps applied:
    1. Parse stringified column values (dicts/lists stored as strings)
    2. Sort by publication_year descending
    3. Keep English-language papers only
    4. Reconstruct abstract from inverted index
    5. Clean abstract text
    6. Compute abstract word count
    7. Extract top keywords from abstract
    8. Build per-word frequency dict from inverted index
    9. Build concepts_array (list of display names)

    Parameters
    ----------
    csv_path : str
        Path to a raw CSV exported from OpenAlex (e.g. data/priority_followed_data_since_2020.csv).
    name : str
        Name of the dataframe to save (e.g. "priority_followed").

    Returns
    -------
    pd.DataFrame with additional columns:
        abstract_raw, abstract, abstract_word_count, abstract_keywords,
        word_frequency, concepts_array
    """
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df):,} papers from {csv_path}")

    # Parse stringified columns
    for col in df.columns:
        df[col] = df[col].map(parse_column)

    # Sort and filter
    df = df.sort_values(by='publication_year', ascending=False)
    df = df[df['language'] == 'en'].copy()
    print(f"After English filter: {len(df):,} papers")

    # Abstract reconstruction and cleaning
    df['abstract_raw'] = df['abstract_inverted_index'].apply(reconstruct_abstract)
    df['abstract'] = df['abstract_raw'].apply(clean_abstract)

    # Derived fields
    df['abstract_word_count'] = df['abstract'].apply(
        lambda x: len(x.split()) if isinstance(x, str) else None
    )
    df['abstract_keywords'] = df['abstract'].apply(
        lambda x: extract_keywords(x) if isinstance(x, str) else None
    )
    df['word_frequency'] = df['abstract_inverted_index'].apply(word_freq_clean)
    df['concepts_array'] = df['concepts'].apply(
        lambda x: [c.get('display_name', '') for c in x] if isinstance(x, list) else []
    )

    # save the cleaned data and cache the dataframe
    df.to_csv(f'data/cleaned/{name}.csv', index=False)
    df.to_pickle(f'data/cleaned/{name}.pkl')

    return df
