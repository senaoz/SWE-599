"""Look up missing BOUN abstracts in Semantic Scholar and Crossref (free tiers, no key, no e-mail).

Raw responses are cached in research/data/v2/boun/ (gitignored) and never committed:
third-party abstracts can carry publisher copyright, and the repository is public.

    .venv/bin/python scripts/fill_abstracts.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))
from src.boun_data import RESEARCH_TYPES  # noqa: E402
from src.text_utils import reconstruct_abstract  # noqa: E402

OUT = RESEARCH / "data" / "v2" / "boun"
S2_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
CR_URL = "https://api.crossref.org/works"


def missing_dois() -> list[str]:
    dois = []
    for line in (OUT / "works_all.jsonl").open():
        w = json.loads(line)
        if w["type"] in RESEARCH_TYPES and w.get("doi") and not reconstruct_abstract(w.get("abstract_inverted_index")):
            dois.append(w["doi"].replace("https://doi.org/", "").lower())
    return sorted(set(dois))


def _cached(path: Path) -> set[str]:
    return {json.loads(line)["doi"] for line in path.open()} if path.exists() else set()


def _post_with_backoff(url, tries=8, **kw):
    for i in range(tries):
        r = requests.post(url, timeout=120, **kw) if "json" in kw else requests.get(url, timeout=120, **kw)
        if r.status_code == 200:
            return r
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(60, 2 ** (i + 1)))
            continue
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    raise RuntimeError(f"gave up after {tries} tries (last HTTP {r.status_code})")


def semantic_scholar(dois: list[str], batch: int = 500) -> None:
    path = OUT / "abstracts_s2.jsonl"
    todo = [d for d in dois if d not in _cached(path)]
    with path.open("a") as f:
        for i in range(0, len(todo), batch):
            chunk = todo[i:i + batch]
            r = _post_with_backoff(S2_URL, params={"fields": "abstract,externalIds"}, json={"ids": [f"DOI:{d}" for d in chunk]})
            for d, p in zip(chunk, r.json()):
                f.write(json.dumps({"doi": d, "found": p is not None, "abstract": (p or {}).get("abstract")}) + "\n")
            f.flush()
            time.sleep(1.5)


def crossref(dois: list[str], batch: int = 50) -> None:
    path = OUT / "abstracts_crossref.jsonl"
    todo = [d for d in dois if d not in _cached(path)]
    with path.open("a") as f:
        for i in range(0, len(todo), batch):
            chunk = todo[i:i + batch]
            r = _post_with_backoff(CR_URL, params={"filter": ",".join(f"doi:{d}" for d in chunk),
                                                   "rows": batch, "select": "DOI,abstract"})
            items = {x["DOI"].lower(): x.get("abstract") for x in r.json()["message"]["items"]}
            for d in chunk:
                f.write(json.dumps({"doi": d, "found": d in items, "abstract": items.get(d)}) + "\n")
            f.flush()
            time.sleep(1.1)


if __name__ == "__main__":
    dois = missing_dois()
    print("missing-abstract DOIs:", len(dois))
    crossref(dois)
    semantic_scholar(dois)
    for name in ("crossref", "s2"):
        rows = [json.loads(line) for line in (OUT / f"abstracts_{name}.jsonl").open()]
        print(name, "found", sum(r["found"] for r in rows), "with abstract", sum(bool(r["abstract"]) for r in rows), "of", len(rows))
