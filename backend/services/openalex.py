from __future__ import annotations

import os
import sys
from datetime import date as date_type
from typing import Any

import pyalex

from backend.config import OPENALEX_EMAIL

# Configure polite pool
if OPENALEX_EMAIL:
    pyalex.config.email = OPENALEX_EMAIL

# Ensure src/ is importable (project root on path)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.text_utils import reconstruct_abstract, clean_abstract, extract_concept_names


_ALLOWED_INSTITUTIONS = [
    {"openalex_id": "https://openalex.org/I63966007",   "display_name": "Massachusetts Institute of Technology", "country_code": "US"},
    {"openalex_id": "https://openalex.org/I97018004",   "display_name": "Stanford University",                   "country_code": "US"},
    {"openalex_id": "https://openalex.org/I136199984",  "display_name": "Harvard University",                    "country_code": "US"},
    {"openalex_id": "https://openalex.org/I95457486",   "display_name": "University of California, Berkeley",   "country_code": "US"},
    {"openalex_id": "https://openalex.org/I27837315",   "display_name": "University of Michigan",               "country_code": "US"},
    {"openalex_id": "https://openalex.org/I1291425158", "display_name": "Google",                               "country_code": "US"},
    {"openalex_id": "https://openalex.org/I4210090411", "display_name": "Google DeepMind",                      "country_code": "GB"},
]


async def search_institutions(query: str, limit: int = 8) -> list[dict[str, Any]]:
    q = query.lower()
    results = [
        inst for inst in _ALLOWED_INSTITUTIONS
        if q in inst["display_name"].lower()
    ]
    return results[:limit]


def fetch_new_papers(
    institution_id: str,
    from_date: str,
    institution_name: str | None = None,
    max_papers: int = 200,
) -> list[dict[str, Any]]:
    """Fetch papers from OpenAlex for an institution since from_date."""
    import logging
    log = logging.getLogger(__name__)

    from pyalex import Works

    filters: dict[str, Any] = {
        "institutions": {"id": institution_id},
        "from_publication_date": from_date,
    }

    log.info("[OpenAlex] Fetching papers for %s since %s", institution_name or institution_id, from_date)

    papers = []
    done = False
    for page in Works().filter(**filters).paginate(per_page=25):
        if done:
            break
        for work in page:
            abstract = None
            inv_index = work.get("abstract_inverted_index")
            if inv_index:
                raw = reconstruct_abstract(inv_index)
                if raw:
                    abstract = clean_abstract(raw)

            concepts = work.get("concepts") or []
            concepts_text = " ".join(
                c.get("display_name", "") for c in concepts if c.get("display_name")
            )

            pub_date_str = work.get("publication_date")
            pub_date = date_type.fromisoformat(pub_date_str) if pub_date_str else None

            papers.append({
                "openalex_id": work["id"],
                "title": work.get("title"),
                "abstract": abstract,
                "concepts_text": concepts_text,
                "publication_date": pub_date,
                "source_institution_name": institution_name,
            })

            if len(papers) >= max_papers:
                done = True
                break

    log.info("[OpenAlex] Fetched %d papers for %s", len(papers), institution_name or institution_id)
    return papers
