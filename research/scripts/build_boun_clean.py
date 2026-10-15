"""Build the cleaned BOUN works table from the 2026-10 OpenAlex refetch.

Writes to research/data/boun/ (tracked with Git LFS):
  works_openalex.jsonl.gz   raw OpenAlex records, all types (CC0)
  boun_works.csv.gz         cleaned research works, one row per duplicate group
  researcher_works.csv.gz   BOUN researcher -> canonical work (full author lists for the
                            works whose list record stopped at 100 authors)
Abstracts from Crossref / Semantic Scholar stay in research/data/v2/boun/ (gitignored):
the table records only their source, not their text.

    .venv/bin/python scripts/build_boun_clean.py
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))
sys.path.insert(0, str(RESEARCH / "audit"))
from data_quality import STRONG, WEAK  # noqa: E402
from src.boun_data import build_clean  # noqa: E402

CACHE = RESEARCH / "data" / "v2" / "boun"
OUT = RESEARCH / "data" / "boun"


def external_abstracts() -> dict[str, tuple[str, str]]:
    """{doi: (source, abstract)}; Crossref first (publisher-deposited), then Semantic Scholar."""
    ext = {}
    for source, name in (("s2", "abstracts_s2.jsonl"), ("crossref", "abstracts_crossref.jsonl")):
        for line in (CACHE / name).open():
            r = json.loads(line)
            if r["abstract"]:
                ext[r["doi"]] = (source, r["abstract"])
    return ext


def main() -> None:
    works = [json.loads(line) for line in (CACHE / "works_all.jsonl").open()]
    full = {r["id"]: r["boun_author_ids"] for r in map(json.loads, (CACHE / "full_authors.jsonl").open())}
    rows, stats = build_clean(works, external_abstracts(), {**STRONG, **WEAK}, full)
    OUT.mkdir(parents=True, exist_ok=True)
    with (CACHE / "works_all.jsonl").open("rb") as src, gzip.open(OUT / "works_openalex.jsonl.gz", "wb") as dst:
        shutil.copyfileobj(src, dst)

    df = pd.DataFrame(rows)
    list_cols = ["topics", "keywords", "concepts", "boun_author_ids", "author_ids", "duplicate_ids", "dq_strong", "dq_weak"]
    for c in list_cols:
        df[c] = df[c].map(json.dumps)
    df.drop(columns=["abstract_external"]).to_csv(OUT / "boun_works.csv.gz", index=False)
    df[["id", "abstract_external", "abstract_source"]].query("abstract_external != ''").to_json(
        CACHE / "external_abstracts_clean.jsonl", orient="records", lines=True)

    pairs = [(a, r["id"]) for r in rows for a in r["boun_author_ids"]]
    pd.DataFrame(pairs, columns=["researcher_id", "work_id"]).to_csv(OUT / "researcher_works.csv.gz", index=False)
    stats.update({"researchers": len({a for a, _ in pairs}), "researcher_work_rows": len(pairs)})
    (OUT / "build_stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
