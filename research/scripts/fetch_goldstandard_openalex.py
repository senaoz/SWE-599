"""Map the Stelmakh et al. gold-standard papers to OpenAlex and cache their reference lists.

Usage (from research/; the key is optional and read from the environment):
    OPENALEX_API_KEY=... .venv/bin/python -I scripts/fetch_goldstandard_openalex.py map    <goldstandard dir>
    OPENALEX_API_KEY=... .venv/bin/python -I scripts/fetch_goldstandard_openalex.py search <goldstandard dir> [--max N]
    OPENALEX_API_KEY=... .venv/bin/python -I scripts/fetch_goldstandard_openalex.py cited  <goldstandard dir> [--go]

map    DOI records and arXiv records (via DOI 10.48550/arxiv.<id>), 50 DOIs per list call.
       Writes data/external/openalex_refs/papers.jsonl, one row per gold-standard paper.
search title search ($0.001 each) for papers with neither id; a hit needs year +-1 and a
       shared author surname.
cited  cited_by_count of every distinct referenced work, plus the number of OpenAlex works with
       at least one reference (the IDF population). Prints the call count and stops unless --go.

Both steps resume from their caches. Downloaded data is never executed.
"""
from __future__ import annotations

import difflib
import glob
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.openalex import request, short_id  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data/external/openalex_refs"
SELECT = "id,doi,ids,locations,title,publication_year,authorships,referenced_works,cited_by_count"
ARXIV = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:v\d+)?(?:\.pdf)?$", re.I)
BATCH = 50
cost = 0.0


def get(params):
    global cost
    body, headers = request(params)
    cost += float(headers.get("X-RateLimit-Cost-USD", headers.get("x-ratelimit-cost-usd", 0)) or 0)
    time.sleep(0.15)
    return body


def norm_doi(d):
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", (d or "").strip().lower())


def surnames(names):
    return {re.sub(r"[^a-z]", "", n.split()[-1].lower()) for n in names if n and n.split()}


def load_papers(G):
    s2 = {}
    for line in open(f"{os.path.dirname(G.rstrip('/'))}/s2_refs/refs.jsonl"):
        r = json.loads(line)
        s2[r["id"]] = r
    ids = set()
    for i in range(1, 11):
        D = f"{G}/evaluation_datasets/d_20_{i}"
        ids |= set(json.load(open(f"{D}/submissions.json")))
        for f in glob.glob(f"{D}/archives/*.jsonl"):
            ids |= {json.loads(line)["id"] for line in open(f)}
    out = {}
    for p in sorted(ids):
        meta = json.load(open(f"{G}/data/papers/{p}.json"))
        out[p] = {"doi": norm_doi(s2[p].get("doi")), "arxiv": meta.get("arXivId"), "title": meta.get("title"),
                  "year": meta.get("year"), "authors": meta.get("authors") or []}
    return out


def record_keys(w):
    """Every DOI the record carries (its own, ids, doi.org locations) as lower-case strings, with
    arXiv ids written as their DOI 10.48550/arxiv.<id>. A filter on one DOI can return a merged
    record whose main DOI is another one, so results are matched to requests through these keys."""
    keys = {norm_doi(w.get("doi")), norm_doi((w.get("ids") or {}).get("doi"))}
    for loc in w.get("locations") or []:
        for url in (loc.get("landing_page_url"), loc.get("pdf_url")):
            url = (url or "").strip()
            if "doi.org/" in url:
                keys.add(norm_doi(url))
            m = ARXIV.search(url)
            if m:
                keys.add(f"10.48550/arxiv.{m.group(1).lower()}")
    return keys - {""}


def slim(w):
    return {"id": short_id(w["id"]), "doi": norm_doi(w.get("doi")), "keys": sorted(record_keys(w)), "title": w.get("title"),
            "year": w.get("publication_year"), "cited_by_count": w.get("cited_by_count"),
            "authors": [(a.get("author") or {}).get("display_name") for a in w.get("authorships") or []],
            "referenced_works": [short_id(r) for r in w.get("referenced_works") or []]}


def by_doi(dois):
    found = {}
    dois = sorted(set(dois))
    for s in range(0, len(dois), BATCH):
        chunk = dois[s:s + BATCH]
        body = get({"filter": "doi:" + "|".join(chunk), "select": SELECT, "per_page": 100})
        for w in body["results"]:
            rec = slim(w)
            for k in set(rec["keys"]) & set(chunk):
                found[k] = rec
        print(f"doi {s + len(chunk)}/{len(dois)} found {len(found)} cost ${cost:.4f}", flush=True)
    return found


def title_ok(orig, found):
    """Same paper by title: normalized similarity >= 0.9, or the shorter title (>= 3 words) is
    contained in the longer one (e.g. a truncated title). Year and surname alone let through
    other papers by the same author."""
    a, b = (re.sub(r"\W+", " ", (t or "").lower()).strip() for t in (orig, found))
    short, long_ = sorted((a, b), key=len)
    return (difflib.SequenceMatcher(None, a, b).ratio() >= 0.9
            or (len(short.split()) >= 3 and f" {short} " in f" {long_} "))


def title_hit(p):
    title = re.sub(r"[^\w\s]", " ", p["title"] or "").strip()
    if not title:
        return None
    body = get({"search": title, "select": SELECT, "per_page": 5})
    want = surnames(p["authors"])
    for w in body["results"]:
        s = slim(w)
        if p["year"] and s["year"] and abs(s["year"] - p["year"]) > 1:
            continue
        if want & surnames(s["authors"]) and title_ok(p["title"], s["title"]):
            return s
    return None


def cmd_map(G):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "papers.jsonl"
    done = {json.loads(line)["id"] for line in open(path)} if path.exists() else set()
    papers = {k: v for k, v in load_papers(G).items() if k not in done}
    doi_hits = by_doi([p["doi"] for p in papers.values() if p["doi"]])
    ax_doi = {k: f"10.48550/arxiv.{p['arxiv'].lower()}" for k, p in papers.items() if p["arxiv"]}
    ax_hits = by_doi(ax_doi.values())
    with path.open("a", encoding="utf-8") as f:
        for k, p in papers.items():
            rec = {"id": k, "doi_record": doi_hits.get(p["doi"]) if p["doi"] else None,
                   "arxiv_record": ax_hits.get(ax_doi.get(k)) if k in ax_doi else None, "title_record": None}
            f.write(json.dumps(rec) + "\n")
    print(f"map done, cost ${cost:.4f}")


def cmd_search(G, limit=None):
    """Title search ($0.001 per call) for papers with neither a DOI nor an arXiv id.

    limit caps the searches in this run (the anonymous budget is $0.10/day); reruns resume.
    """
    path = OUT / "papers.jsonl"
    rows = [json.loads(line) for line in open(path)]
    papers = load_papers(G)
    for r in rows:
        if r.get("title_record") and not title_ok(papers[r["id"]]["title"], r["title_record"]["title"]):
            print(f"rejected: {papers[r['id']]['title'][:60]!r} -> {r['title_record']['title'][:60]!r}")
            r["title_record"] = None
    todo = [r for r in rows if not papers[r["id"]]["doi"] and not papers[r["id"]]["arxiv"] and "searched" not in r]
    print(f"title searches left {len(todo)}, this run {min(len(todo), limit or len(todo))}")
    todo = todo[:limit]
    for i, r in enumerate(todo):
        r["title_record"] = title_hit(papers[r["id"]])
        r["searched"] = True
        if i % 20 == 0:
            print(f"search {i + 1}/{len(todo)} cost ${cost:.4f}", flush=True)
            path.write_text("".join(json.dumps(x) + "\n" for x in rows))
    path.write_text("".join(json.dumps(x) + "\n" for x in rows))
    print(f"search done, cost ${cost:.4f}")


def cmd_cited(G, go):
    rows = [json.loads(line) for line in open(OUT / "papers.jsonl")]
    refs = {r for row in rows for k in ("doi_record", "arxiv_record", "title_record") if row[k]
            for r in row[k]["referenced_works"]}
    path = OUT / "cited_by.jsonl"
    have = {json.loads(line)["id"] for line in open(path)} if path.exists() else set()
    todo = sorted(refs - have)
    calls = -(-len(todo) // BATCH)
    print(f"distinct referenced works {len(refs)}, to fetch {len(todo)}, list calls {calls}, "
          f"estimated ${calls * 0.0001:.4f} (at $0.0001 per list call)")
    if not go:
        return
    with path.open("a", encoding="utf-8") as f:
        for s in range(0, len(todo), BATCH):
            chunk = todo[s:s + BATCH]
            body = get({"filter": "openalex_id:" + "|".join(chunk), "select": "id,cited_by_count", "per_page": 100})
            got = {short_id(w["id"]): w["cited_by_count"] for w in body["results"]}
            for w in chunk:
                f.write(json.dumps({"id": w, "cited_by_count": got.get(w)}) + "\n")
            if (s // BATCH) % 20 == 0:
                print(f"cited {s + len(chunk)}/{len(todo)} cost ${cost:.4f}", flush=True)
    meta = get({"filter": "referenced_works_count:>0", "per_page": 1, "select": "id"})["meta"]
    (OUT / "population.json").write_text(json.dumps({"works_with_references": meta["count"],
                                                     "fetched": time.strftime("%Y-%m-%d")}))
    print(f"population {meta['count']}, cost ${cost:.4f}")


if __name__ == "__main__":
    step, G = sys.argv[1], sys.argv[2]
    if step == "map":
        cmd_map(G)
    elif step == "search":
        cmd_search(G, int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else None)
    elif step == "cited":
        cmd_cited(G, "--go" in sys.argv)
    else:
        raise SystemExit(f"unknown step {step}")
