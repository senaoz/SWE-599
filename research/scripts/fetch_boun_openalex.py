"""Refetch BOUN works from OpenAlex into research/data/v2/boun/ (gitignored).

Same filter as v1/01 (BOUN lineage, articles, 2020+); language is filtered later.
`boun.csv` is left untouched.

    OPENALEX_API_KEY=... .venv/bin/python scripts/fetch_boun_openalex.py count
    OPENALEX_API_KEY=... .venv/bin/python scripts/fetch_boun_openalex.py fetch
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))
from src.openalex import request  # noqa: E402

OUT = RESEARCH / "data" / "v2" / "boun"
FILTER = "authorships.institutions.lineage:i4405392,type:article,publication_year:2020-"
SELECT = ("id,doi,ids,title,publication_date,publication_year,language,type,authorships,"
          "abstract_inverted_index,concepts,topics,primary_topic,keywords,referenced_works,"
          "referenced_works_count,cited_by_count,is_retracted,is_paratext,updated_date")


def count() -> int:
    data, _ = request({"filter": FILTER, "per_page": 1, "select": "id"})
    return data["meta"]["count"]


def fetch(sleep: float = 0.2) -> None:
    """Cursor paging, resumable: the next cursor is saved after every page."""
    OUT.mkdir(parents=True, exist_ok=True)
    works_path, cursor_path = OUT / "works.jsonl", OUT / "cursor.json"
    seen = set()
    if works_path.exists():
        seen = {json.loads(line)["id"] for line in works_path.open()}
    cursor = json.loads(cursor_path.read_text())["cursor"] if cursor_path.exists() else "*"
    calls = 0
    with works_path.open("a", encoding="utf-8") as f:
        while cursor:
            data, _ = request({"filter": FILTER, "per_page": 100, "cursor": cursor, "select": SELECT})
            calls += 1
            for w in data["results"]:
                if w["id"] not in seen:
                    seen.add(w["id"])
                    f.write(json.dumps(w) + "\n")
            f.flush()
            cursor = data["meta"].get("next_cursor") if data["results"] else None
            cursor_path.write_text(json.dumps({"cursor": cursor, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S")}))
            time.sleep(sleep)
    print(f"done: {len(seen)} works, {calls} list calls this run")


if __name__ == "__main__":
    {"count": lambda: print("count:", count()), "fetch": fetch}[sys.argv[1]]()
