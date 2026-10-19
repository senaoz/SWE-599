"""Data for the BOUN-side coupling description (notebook 15, Experiment B).

Usage (from research/):
    .venv/bin/python -I scripts/experiment_b_data.py sample   # 2 OpenAlex list calls, about $0.0002
    .venv/bin/python -I scripts/experiment_b_data.py embed    # Qwen3-Embedding-8B, resumable

sample  The 200 most recent articles (publication date up to today) from the followed institutions
        that have an abstract and no BOUN author. Written to data/external/followed_sample/works.jsonl.
embed   Embeds the cleaned BOUN works and the sample (title + abstract) in chunks of 256, saving the
        cache after each chunk, so an interrupted run resumes.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))
from src.boun_data import BOUN, work_texts  # noqa: E402
from src.openalex import PRIORITY_FILTER, normalize_work, request  # noqa: E402
from src.rankers_v2 import EmbeddingCache  # noqa: E402

SAMPLE = RESEARCH / "data" / "external" / "followed_sample" / "works.jsonl"
CACHE = RESEARCH / "data" / "v2" / "embeddings_boun"
N_SAMPLE = 200
CHUNK = 256


def has_boun_author(w: dict) -> bool:
    return any(BOUN in (inst.get("lineage") or []) or inst.get("id") == BOUN
               for a in w.get("authorships") or [] for inst in a.get("institutions") or [])


def sample_text(w: dict) -> str:
    return f"{w['title']} {w['abstract']}".strip()


def cmd_sample():
    today = time.strftime("%Y-%m-%d")
    params = {"filter": f"{PRIORITY_FILTER},has_abstract:true,to_publication_date:{today}",
              "sort": "publication_date:desc", "per_page": 100,
              "select": "id,title,publication_date,authorships,abstract_inverted_index,referenced_works,"
                        "concepts,language,type"}
    out, cost, page = [], 0.0, 1
    while len(out) < N_SAMPLE and page <= 4:
        body, headers = request({**params, "page": page})
        cost += float(headers.get("X-RateLimit-Cost-USD", 0) or 0)
        out += [w for w in body["results"] if not has_boun_author(w)]
        page += 1
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLE.open("w", encoding="utf-8") as f:
        for w in out[:N_SAMPLE]:
            f.write(json.dumps({**normalize_work(w), "fetched": today}) + "\n")
    print(f"sample {min(len(out), N_SAMPLE)} works, {page - 1} calls, cost ${cost:.4f}")


def cmd_embed():
    texts = list(work_texts(RESEARCH).values())
    texts += [sample_text(json.loads(line)) for line in open(SAMPLE)]
    cache = EmbeddingCache("qwen", CACHE)
    todo = sorted({t for t in texts if cache.key(t) not in cache.vectors})
    print(f"texts {len(set(texts))}, to embed {len(todo)}", flush=True)
    for s in range(0, len(todo), CHUNK):
        cache.ensure(todo[s:s + CHUNK])
        print(f"embedded {min(s + CHUNK, len(todo))}/{len(todo)}", flush=True)


if __name__ == "__main__":
    {"sample": cmd_sample, "embed": cmd_embed}[sys.argv[1]]()
