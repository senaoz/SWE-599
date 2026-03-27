import ast
import html
import re


def safe_parse(val):
    """Safely parse stringified lists/dicts using ast.literal_eval."""
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except Exception:
            return val
    return val


def reconstruct_abstract(inv_index):
    """Rebuild abstract text from OpenAlex ``abstract_inverted_index`` (same as fetch_and_preprocessing)."""
    if not isinstance(inv_index, dict):
        return None
    words = []
    for word, positions in inv_index.items():
        for pos in positions:
            words.append((pos, word))
    words = sorted(words)
    return " ".join(w[1] for w in words)


def clean_abstract(text):
    """Normalize abstract string after reconstruction (same rules as fetch_and_preprocessing)."""
    if not isinstance(text, str):
        return None
    text = html.unescape(text)
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\bABSTRACT\b", "", text)
    text = re.sub(r"\bAbstract\b", "", text)
    return text.strip()


def extract_concept_names(val):
    """Extract concept display names from the concepts column."""
    parsed = safe_parse(val)
    if isinstance(parsed, list):
        return ' '.join(c.get('display_name', '') for c in parsed if isinstance(c, dict))
    return ''


def build_text(row, fields=('abstract', 'title', 'concepts')):
    """Build text representation from selected fields.

    Parameters
    ----------
    row : dict-like
        Paper row with 'title', 'abstract', 'concepts' keys.
    fields : tuple of str
        Any combination of 'abstract', 'title', 'concepts'. Default: all three.
    """
    parts = []
    if 'title' in fields and isinstance(row.get('title'), str) and row['title']:
        parts.append(row['title'])
    if 'abstract' in fields and isinstance(row.get('abstract'), str) and row['abstract']:
        parts.append(row['abstract'])
    if 'concepts' in fields:
        ct = extract_concept_names(row.get('concepts', ''))
        if ct.strip():
            parts.append(ct)
    return ' '.join(parts)
