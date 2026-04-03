"""
OpenAlex client for the Scholar Notification & BOUN Researcher Matching System.

Uses the OpenAlex API (via pyalex) to:
- Resolve BOUN (Boğaziçi University) and other institutions/publishers
- Fetch BOUN researchers and their publications (local corpus)
- Fetch new works from followed sources (trigger for matching)
"""

from __future__ import annotations

import os
from typing import Any, Iterator

import pyalex
from pyalex import Institutions, Works, Authors


# Optional: set email for polite pool (faster, more consistent responses)
# https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication
if os.environ.get("OPENALEX_EMAIL"):
    pyalex.config.email = os.environ["OPENALEX_EMAIL"]


# Default OpenAlex ID for Boğaziçi University (resolved via search; override if needed)
BOUN_OPENALEX_ID = "https://openalex.org/I4405392"

# Followed institutions: top CS universities and industry labs
FOLLOWED_INSTITUTIONS: dict[str, dict[str, str]] = {
    "MIT":        {"openalex_id": "I63966007",  "ror_id": "042nb2s44", "display_name": "MIT"},
    "Stanford":   {"openalex_id": "I97018004",  "ror_id": "00f54p054", "display_name": "Stanford University"},
    "Harvard":    {"openalex_id": "I136199984", "ror_id": "03vek6s52", "display_name": "Harvard University"},
    "UC Berkeley":{"openalex_id": "I95457486",  "ror_id": "01an7q238", "display_name": "UC Berkeley"},
    "Caltech":    {"openalex_id": "I132025700", "ror_id": "05dxps055", "display_name": "Caltech"},
    "CMU":        {"openalex_id": "I74201158",  "ror_id": "01f4asq49", "display_name": "Carnegie Mellon University"},
    "Princeton":  {"openalex_id": "I20089843",  "ror_id": "00hx57361", "display_name": "Princeton University"},
    "Cornell":    {"openalex_id": "I205783295", "ror_id": "05bnh6r87", "display_name": "Cornell University"},
    "Columbia":   {"openalex_id": "I130701444", "ror_id": "00hj8hs39", "display_name": "Columbia University"},
    "Google":     {"openalex_id": "I4210103108","ror_id": "047s64r39", "display_name": "Google"},
    "Microsoft":  {"openalex_id": "I4210106411","ror_id": "0368v0h10", "display_name": "Microsoft"},
    "Meta":       {"openalex_id": "I4210086253","ror_id": "033dq7834", "display_name": "Meta (Facebook)"},
    "IBM":        {"openalex_id": "I4210113641","ror_id": "01416x027", "display_name": "IBM"},
    "OpenAI":     {"openalex_id": "I4210161460","ror_id": "05wx9n238", "display_name": "OpenAI"},
    "NVIDIA":     {"openalex_id": "I4210137257","ror_id": "0299vnb19", "display_name": "NVIDIA"},
    "Amazon":     {"openalex_id": "I4210149028","ror_id": "041f0t860", "display_name": "Amazon"},
    "Apple":      {"openalex_id": "I4210108604","ror_id": "006w34k90", "display_name": "Apple"},
    "Oxford":     {"openalex_id": "I40120149",  "ror_id": "052gg0110", "display_name": "Oxford University"},
    "Cambridge":  {"openalex_id": "I241749",    "ror_id": "013meh722", "display_name": "Cambridge University"},
    "ETH Zurich": {"openalex_id": "I201448701", "ror_id": "05a0d1q62", "display_name": "ETH Zurich"},
    "TUM":        {"openalex_id": "I157725225", "ror_id": "02kkvkv10", "display_name": "TU Munich"},
    "DeepMind":   {"openalex_id": "I4210126451","ror_id": "030796853", "display_name": "DeepMind"},
    "UofToronto": {"openalex_id": "I185261750", "ror_id": "03dbr7087", "display_name": "University of Toronto"},
    "Tsinghua":   {"openalex_id": "I159176309", "ror_id": "03bk6pm13", "display_name": "Tsinghua University"},
    "NUS":        {"openalex_id": "I165143802", "ror_id": "024760920", "display_name": "NUS (Singapore)"},
}

def get_followed_openalex_ids() -> list[str]:
    """Return full OpenAlex URLs for all followed institutions."""
    return [f"https://openalex.org/{v['openalex_id']}" for v in FOLLOWED_INSTITUTIONS.values()]


def find_institution(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search OpenAlex for institutions by name (e.g. 'Boğaziçi University', 'Stanford')."""
    results = list(Institutions().search(query).get(per_page=limit))
    return [{"id": r["id"], "display_name": r.get("display_name"), "country_code": r.get("country_code")} for r in results]

def works_from_institution(
    institution_id: str,
    *,
    from_publication_date: str | None = None,
    to_publication_date: str | None = None,
    per_page: int = 25,
) -> Iterator[dict[str, Any]]:
    """
    Stream works where at least one author is associated with the given institution.

    institution_id: OpenAlex institution ID (e.g. from find_institution)
    from_publication_date / to_publication_date: YYYY-MM-DD for filtering new releases
    """
    filters: dict[str, Any] = {"institutions": {"id": institution_id}}
    if from_publication_date:
        filters["from_publication_date"] = from_publication_date
    if to_publication_date:
        filters["to_publication_date"] = to_publication_date

    return Works().filter(**filters).paginate(per_page=per_page)


def works_from_source(
    source_id: str,
    *,
    from_publication_date: str | None = None,
    to_publication_date: str | None = None,
    per_page: int = 25,
) -> Iterator[dict[str, Any]]:
    """
    Stream works from a given source (journal/venue).

    source_id: OpenAlex source ID (e.g. https://openalex.org/S12345678)
    """
    filters: dict[str, Any] = {"primary_location": {"source": {"id": source_id}}}
    if from_publication_date:
        filters["from_publication_date"] = from_publication_date
    if to_publication_date:
        filters["to_publication_date"] = to_publication_date

    return Works().filter(**filters).paginate(per_page=per_page)


def work_to_text(work: dict[str, Any]) -> str:
    """Extract title + abstract for embedding (Week 1 benchmark / similarity)."""
    title = work.get("title") or ""
    abstract = ""
    if work.get("abstract_inverted_index"):
        # OpenAlex stores abstract as inverted index; rebuild plain text if needed
        # For simplicity we use the first 500 chars of raw if available, else skip
        pass
    # OpenAlex often has no plain abstract; use title and optionally biblio
    return title.strip()


def authors_from_institution(
    institution_id: str,
    *,
    per_page: int = 25,
) -> Iterator[dict[str, Any]]:
    """Stream authors associated with the given institution (e.g. BOUN researchers)."""
    return Authors().filter(last_known_institutions={"id": institution_id}).paginate(
        per_page=per_page
    )


def sample_boun_works(limit: int = 10, publication_year: int | None = None) -> list[dict[str, Any]]:
    """
    Fetch a small sample of BOUN works for testing and benchmark dataset building.

    Useful for Week 1: building a benchmark to evaluate embedding models.
    """
    boun_id = BOUN_OPENALEX_ID
    filters: dict[str, Any] = {"institutions": {"id": boun_id}}
    if publication_year is not None:
        filters["publication_year"] = publication_year
    results = list(Works().filter(**filters).sort(publication_date="desc").get(per_page=limit))
    return results


def sample_new_works_from_sources(
    source_ids: list[str],
    from_publication_date: str,
    limit_per_source: int = 20,
) -> list[dict[str, Any]]:
    """
    Fetch recent works from a list of followed sources (e.g. journals/publishers).

    from_publication_date: YYYY-MM-DD to simulate "new releases" trigger.
    """
    out: list[dict[str, Any]] = []
    for sid in source_ids:
        count = 0
        for work in works_from_source(sid, from_publication_date=from_publication_date):
            out.append(work)
            count += 1
            if count >= limit_per_source:
                break
    return out