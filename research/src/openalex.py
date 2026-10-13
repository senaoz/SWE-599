"""OpenAlex fetching and normalization for the v2 benchmark.

Every paper — query, positive, negative — goes through `normalize_work`, so all
candidates carry the same fields regardless of where they came from.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from src.text_utils import clean_abstract, reconstruct_abstract

API = "https://api.openalex.org/works"
SELECT = ("id,title,publication_date,publication_year,language,type,concepts,"
          "authorships,abstract_inverted_index,referenced_works")
BATCH = 50  # ids per filter request (OpenAlex allows up to 100)

# Priority-followed institutions (lineage), same filter as fetch_and_preprocessing.ipynb.
PRIORITY_FILTER = ("authorships.institutions.lineage:i97018004|i136199984|i95457486|"
                   "i1291425158|i4210090411|i27837315|i63966007,type:article,publication_year:2020-")


def short_id(work_id: str) -> str:
    return work_id.rsplit("/", 1)[-1]


class OpenAlexError(RuntimeError):
    pass


def request(params: dict, retries: int = 4) -> tuple[dict, dict]:
    """GET /works; returns (json body, rate-limit headers).

    Adds OPENALEX_API_KEY from the environment when set. Errors never carry the
    request URL, so the key cannot reach logs, notebooks or tracebacks.
    """
    key = os.getenv("OPENALEX_API_KEY")
    query = {**params, "api_key": key} if key else params
    for attempt in range(retries):
        try:
            resp = requests.get(API, params=query, timeout=60)
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise OpenAlexError(f"request failed: {type(e).__name__}") from None
        if resp.status_code == 200:
            headers = {k: v for k, v in resp.headers.items() if k.lower().startswith("x-ratelimit")}
            return resp.json(), headers
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
            time.sleep(2 ** attempt)
            continue
        raise OpenAlexError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    raise RuntimeError("unreachable")


def _get(params: dict, retries: int = 4) -> dict:
    return request(params, retries)[0]


def _read_jsonl(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {w["id"]: w for w in map(json.loads, f)}


def fetch_works_by_id(ids, cache_path: Path, sleep: float = 0.2) -> dict[str, dict]:
    """Fetch raw works by OpenAlex id, appending to a JSONL cache. Returns {id: raw work}."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    works = _read_jsonl(cache_path)
    missing = sorted({i for i in ids if i not in works})
    with cache_path.open("a", encoding="utf-8") as f:
        for start in range(0, len(missing), BATCH):
            batch = missing[start:start + BATCH]
            data = _get({"filter": "openalex_id:" + "|".join(map(short_id, batch)),
                         "per_page": BATCH, "select": SELECT})
            for w in data["results"]:
                if w["id"] not in works:
                    works[w["id"]] = w
                    f.write(json.dumps(w) + "\n")
            time.sleep(sleep)
    return works


def fetch_corpus(cache_path: Path, limit: int, sleep: float = 0.2) -> dict[str, dict]:
    """Fetch the priority-followed corpus with cursor paging (basic paging stops at 10,000)."""
    if cache_path.exists():
        return _read_jsonl(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    works, cursor = {}, "*"
    with cache_path.open("w", encoding="utf-8") as f:
        while cursor and len(works) < limit:
            data = _get({"filter": PRIORITY_FILTER, "per_page": 200,
                         "cursor": cursor, "select": SELECT})
            for w in data["results"]:
                if len(works) < limit and w["id"] not in works:
                    works[w["id"]] = w
                    f.write(json.dumps(w) + "\n")
            cursor = data["meta"].get("next_cursor") if data["results"] else None
            time.sleep(sleep)
    return works


def normalize_work(w: dict) -> dict:
    """Map a raw OpenAlex work to the fields every candidate shares."""
    raw = reconstruct_abstract(w.get("abstract_inverted_index"))
    authors = sorted({a["author"]["id"] for a in w.get("authorships") or []
                      if (a.get("author") or {}).get("id")})
    return {
        "id": w["id"],
        "title": clean_abstract(w.get("title") or "") or "",
        "abstract": (clean_abstract(raw) or "") if raw else "",
        "concepts_array": [c["display_name"] for c in w.get("concepts") or [] if c.get("display_name")],
        "publication_date": w.get("publication_date") or "",
        "author_ids": authors,
        "language": w.get("language") or "",
        "type": w.get("type") or "",
        "referenced_works": w.get("referenced_works") or [],
    }
