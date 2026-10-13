"""Phase 5 data: citer pool and candidate corpus (research/audit/PHASE5_DESIGN.md).

- Citer pool: for each query, an OpenAlex title search restricted to works published
  before the query with at least 10 references. Selection reads only the query's title,
  never its references, so the graph is not built around the answer key.
- Candidate corpus: all eligible positives plus the works cited by at least m pool
  citers (query records never count as citers); m is chosen from corpus size alone.

Raw responses are cached under data/v2/corpus/, so reruns cost no API calls.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from src.openalex import request, short_id

RESEARCH = Path(__file__).resolve().parents[1]
CORPUS_DATA = RESEARCH / "data" / "v2" / "corpus"
WORKS = CORPUS_DATA / "works.jsonl"
NOT_FOUND = CORPUS_DATA / "works_not_found.json"
CITERS = CORPUS_DATA / "citers"

WORK_SELECT = ("id,doi,ids,title,publication_date,publication_year,language,type,concepts,"
               "authorships,abstract_inverted_index,referenced_works")
CITER_SELECT = "id,doi,title,publication_date,type,authorships,referenced_works"
ID_BATCH = 100      # OpenAlex allows up to 100 OR values per filter
CITERS_PER_QUERY = 100  # one search page (per_page max is 100); P0: page 2 added no positive
MIN_CITER_REFS = 10


def search_terms(title: str) -> str:
    return re.sub(r"[^\w\s-]", " ", title).strip()


def _read_jsonl(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {w["id"]: w for w in map(json.loads, f)}


def fetch_works(ids, sleep: float = 0.1) -> tuple[dict[str, dict], set[str]]:
    """Raw works by id (wide select, with doi and ids), appended to one JSONL cache.

    Ids OpenAlex does not return (deleted or merged) are remembered, so they are not
    requested again. Returns ({id: raw work}, not-found ids among `ids`).
    """
    CORPUS_DATA.mkdir(parents=True, exist_ok=True)
    works = _read_jsonl(WORKS)
    not_found = set(json.loads(NOT_FOUND.read_text())) if NOT_FOUND.exists() else set()
    todo = sorted({i for i in ids if i not in works and i not in not_found})
    with WORKS.open("a", encoding="utf-8") as f:
        for start in range(0, len(todo), ID_BATCH):
            batch = todo[start:start + ID_BATCH]
            body, _ = request({"filter": "openalex_id:" + "|".join(map(short_id, batch)),
                               "per_page": ID_BATCH, "select": WORK_SELECT})
            returned = set()
            for w in body["results"]:
                returned.add(w["id"])
                if w["id"] not in works:
                    works[w["id"]] = w
                    f.write(json.dumps(w) + "\n")
            not_found |= set(batch) - returned
            NOT_FOUND.write_text(json.dumps(sorted(not_found)))
            time.sleep(sleep)
    wanted = set(ids)
    return {i: works[i] for i in wanted if i in works}, wanted & not_found


def fetch_citers(qid: str, title: str, pub_date: str) -> dict:
    """One title search per query: works published before it with >= 10 references."""
    path = CITERS / f"{short_id(qid)}.json"
    if path.exists():
        return json.loads(path.read_text())
    before = (date.fromisoformat(pub_date) - timedelta(days=1)).isoformat()
    params = {"search": search_terms(title),
              "filter": f"to_publication_date:{before},referenced_works_count:>{MIN_CITER_REFS - 1}",
              "per_page": CITERS_PER_QUERY, "select": CITER_SELECT}
    body, headers = request(params)
    out = {"pi_id": qid, "fetched": date.today().isoformat(), "params": params,
           "count": body["meta"]["count"], "cost_usd": headers.get("X-RateLimit-Cost-USD"),
           "results": body["results"]}
    CITERS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def citer_pool(searches: list[dict]) -> dict[str, dict]:
    """Union of all searches by citer id; `found_for` lists the queries whose search returned it."""
    pool: dict[str, dict] = {}
    for s in searches:
        for w in s["results"]:
            rec = pool.setdefault(w["id"], {**w, "found_for": []})
            rec["found_for"].append(s["pi_id"])
    return pool


def ref_counts(pool: dict[str, dict], exclude: set[str]) -> Counter:
    """How many pool citers (outside `exclude`) cite each work."""
    return Counter(r for cid, w in pool.items() if cid not in exclude
                   for r in set(w["referenced_works"]))


def positive_coverage(sets: list[dict], pool: dict[str, dict], exclude: set[str]) -> list[dict]:
    """Per query: positives cited by at least one allowed citer (not excluded, published before the query)."""
    cited_by: dict[str, list[str]] = {}
    for cid, w in pool.items():
        if cid in exclude or not w.get("publication_date"):
            continue
        for r in set(w["referenced_works"]):
            cited_by.setdefault(r, []).append(w["publication_date"])
    rows = []
    for s in sets:
        n_cov = sum(any(d < s["pi_date"] for d in cited_by.get(p, ())) for p in s["positives"])
        rows.append({"pi_id": s["pi_id"], "n_pos": len(s["positives"]), "n_covered": n_cov})
    return rows
