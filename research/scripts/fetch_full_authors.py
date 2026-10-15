"""Full author lists for BOUN works whose list-endpoint record was cut at 100 authorships.

Single-work calls return every authorship (free on the OpenAlex pricing as of 2026-10-15).
Only BOUN authorships are kept, in research/data/v2/boun/full_authors.jsonl (resumable).

    OPENALEX_API_KEY=... .venv/bin/python scripts/fetch_full_authors.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))
from src.boun_data import boun_author_ids  # noqa: E402

CACHE = RESEARCH / "data" / "v2" / "boun"


def main(sleep: float = 0.15) -> None:
    out = CACHE / "full_authors.jsonl"
    done = {json.loads(line)["id"] for line in out.open()} if out.exists() else set()
    todo = [w["id"] for w in map(json.loads, (CACHE / "works_all.jsonl").open())
            if len(w.get("authorships") or []) >= 100 and w["id"] not in done]
    print("to fetch:", len(todo))
    key = os.getenv("OPENALEX_API_KEY")
    with out.open("a") as f:
        for n, wid in enumerate(todo, 1):
            for attempt in range(5):
                r = requests.get(f"https://api.openalex.org/works/{wid.rsplit('/', 1)[1]}",
                                 params={"select": "id,authorships", **({"api_key": key} if key else {})}, timeout=120)
                if r.status_code == 200:
                    break
                if r.status_code not in (429, 500, 502, 503, 504) or attempt == 4:
                    raise RuntimeError(f"HTTP {r.status_code} for {wid}")
                time.sleep(2 ** attempt)
            w = r.json()
            f.write(json.dumps({"id": wid, "n_authorships": len(w["authorships"]),
                                "boun_author_ids": boun_author_ids(w)}) + "\n")
            f.flush()
            if n % 100 == 0:
                print(n, "done", flush=True)
            time.sleep(sleep)


if __name__ == "__main__":
    main()
