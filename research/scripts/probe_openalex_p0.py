"""Phase 5, step P0: size the citer pool and candidate corpus before any bulk fetch.

Uses 4 dev queries only (never test). About 7 OpenAlex calls; every raw response
and its rate-limit headers are cached under data/v2/probe/, so re-running costs nothing.

    .venv/bin/python scripts/probe_openalex_p0.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import requests

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))

from src.eval_v2 import eligible, rng_for  # noqa: E402
from src.openalex import API, normalize_work, short_id  # noqa: E402

PROBE = RESEARCH / "data" / "v2" / "probe"
RAW_WORKS = RESEARCH / "data" / "v2" / "openalex_works.jsonl"
EVAL_SET = RESEARCH / "v2" / "eval_sets" / "eval_sets_random.json"

# Chosen for topic spread (clinical trial, early COVID, CS, AI in health), before any result was seen.
DEV_QUERIES = ["W3081830235", "W3010209825", "W4200150166", "W3183015861"]
CITER_SELECT = "id,doi,title,publication_date,type,authorships,referenced_works"
WORK_SELECT = ("id,doi,ids,title,publication_date,publication_year,language,type,concepts,"
               "authorships,abstract_inverted_index,referenced_works")


def call(name: str, params: dict) -> dict:
    """GET once and cache body + rate-limit headers; later runs read the cache."""
    path = PROBE / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    resp = requests.get(API, params=params, timeout=60)
    headers = {k: v for k, v in resp.headers.items() if k.lower().startswith("x-ratelimit")}
    if resp.status_code != 200:
        raise RuntimeError(f"{name}: HTTP {resp.status_code} {resp.text[:300]}")
    out = {"params": params, "headers": headers, "url": resp.url, "body": resp.json()}
    PROBE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def search_terms(title: str) -> str:
    return re.sub(r"[^\w\s-]", " ", title).strip()


def main() -> None:
    ds = json.loads(EVAL_SET.read_text())
    papers = ds["papers"]
    sets = {short_id(s["pi_id"]): s for s in ds["sets"]}
    assert all(ds["splits"][sets[q]["pi_id"]] == "dev" for q in DEV_QUERIES)
    query_ids = {s["pi_id"] for s in ds["sets"]}
    cached = {json.loads(l)["id"] for l in RAW_WORKS.open()}

    # 1. One 100-id OR filter with the wider select (doi, ids): does the URL and the limit work?
    ids100 = sorted(cached)[:100]
    r = call("01_ids100", {"filter": "openalex_id:" + "|".join(map(short_id, ids100)),
                           "per_page": 100, "select": WORK_SELECT})
    got = {w["id"] for w in r["body"]["results"]}
    print(f"[1] 100-id filter: {len(got)}/100 returned, URL {len(r['url'])} chars, "
          f"doi present {sum(bool(w.get('doi')) for w in r['body']['results'])}/{len(got)}")
    print("    headers:", r["headers"])

    # 2. Per-query title search for citers published before the query.
    pool: dict[str, dict] = {}
    for q in DEV_QUERIES:
        s = sets[q]
        before = (date.fromisoformat(s["pi_date"]) - timedelta(days=1)).isoformat()
        r = call(f"02_search_{q}", {"search": search_terms(s["pi_title"]),
                                    "filter": f"to_publication_date:{before},referenced_works_count:>9",
                                    "per_page": 100, "select": CITER_SELECT})
        res = r["body"]["results"]
        pos = set(s["positives"])
        cites_pos = Counter(p for w in res for p in w["referenced_works"] if p in pos)
        own_title = re.sub(r"\W+", " ", s["pi_title"].lower()).strip()
        same_title = [w["id"] for w in res if re.sub(r"\W+", " ", (w["title"] or "").lower()).strip() == own_title]
        print(f"[2] {q} ({s['pi_date']}, {len(pos)} positives): count={r['body']['meta']['count']}, "
              f"returned={len(res)}, positives with >=1 citer={len(cites_pos)}/{len(pos)}, "
              f"query records in results={sum(w['id'] in query_ids for w in res)}, "
              f"same-title records={same_title}, years={min((w['publication_date'] or '9')[:4] for w in res) if res else '-'}"
              f"–{max((w['publication_date'] or '0')[:4] for w in res) if res else '-'}")
        print(f"    cost headers: {r['headers']}")
        for w in res:
            pool.setdefault(w["id"], w)

    # 3. Second page for one query: is depth 200 worth a second search call?
    q = DEV_QUERIES[0]
    s = sets[q]
    before = (date.fromisoformat(s["pi_date"]) - timedelta(days=1)).isoformat()
    r = call(f"03_search_{q}_p2", {"search": search_terms(s["pi_title"]),
                                   "filter": f"to_publication_date:{before},referenced_works_count:>9",
                                   "per_page": 100, "page": 2, "select": CITER_SELECT})
    res2 = r["body"]["results"]
    pos = set(s["positives"])
    p1 = {p for w in pool.values() for p in w["referenced_works"] if p in pos}
    p2 = {p for w in res2 for p in w["referenced_works"] if p in pos}
    print(f"[3] {q} page 2: returned={len(res2)}, positives first reached on page 2: {len(p2 - p1)}")

    # 4. Corpus size: references of the probe pool, by how many pool citers cite them.
    ref_counts = Counter(p for w in pool.values() for p in set(w["referenced_works"]))
    for m in (1, 2, 3, 5):
        print(f"[4] refs cited by >= {m} of {len(pool)} pool citers: {sum(c >= m for c in ref_counts.values())}")

    # 5. Abstract/title eligibility of non-cached references (seeded sample of 100).
    uncached = sorted(set(ref_counts) - cached)
    rng = rng_for("p0-eligibility")
    sample = [uncached[i] for i in sorted(rng.choice(len(uncached), size=100, replace=False))]
    r = call("05_eligibility", {"filter": "openalex_id:" + "|".join(map(short_id, sample)),
                                "per_page": 100, "select": WORK_SELECT})
    recs = [normalize_work(w) for w in r["body"]["results"]]
    print(f"[5] eligibility sample: {len(recs)}/100 returned, title+abstract {sum(map(eligible, recs))}/{len(recs)}, "
          f"with date {sum(bool(x['publication_date']) for x in recs)}/{len(recs)}")


if __name__ == "__main__":
    main()
