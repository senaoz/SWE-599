"""v2 evaluation sets: leak-free candidate pools, splits and candidate orders.

Fixes for the v1 audit (research/audit/AUDIT.md):
- F6: every candidate is looked up by OpenAlex id in one normalized table and
  asserted to carry that id, so text can never come from another paper.
- F4: positives and negatives come from the same table via the same function,
  so they have identical fields; candidate text is built by `paper_text`.
- F8: all randomness is seeded through sha256, not Python's salted hash().
- F1: candidate order is a separate, recorded step (`candidate_order`).
- Negatives are other queries' references published before the query paper,
  so positives and negatives share the same "cited work" distribution.
"""
from __future__ import annotations

import hashlib
import re

import numpy as np

MIN_POSITIVES = 3
NEG_PER_POS = 2
DEV_FRACTION = 0.3
ORDER_MODES = ("shuffled", "original", "reversed")


def stable_seed(*parts) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def rng_for(*parts) -> np.random.Generator:
    return np.random.default_rng(stable_seed(*parts))


def eligible(rec: dict) -> bool:
    """Same requirement for queries, positives and negatives."""
    return bool(rec["title"] and rec["abstract"])


def build_eval_sets(main_papers: list[dict], papers: dict[str, dict], seed: int = 0) -> dict:
    """Build per-query candidate pools.

    main_papers: the 174 v1 query records (id + referenced_works ground truth).
    papers: {openalex id: normalize_work(...)} for queries and all references.
    """
    for pid, rec in papers.items():
        assert rec["id"] == pid, f"paper table key/id mismatch: {pid} vs {rec['id']}"

    query_ids = {p["id"] for p in main_papers}
    pool = sorted(
        pid for p in main_papers for pid in p["referenced_works"]
        if pid in papers and pid not in query_ids and eligible(papers[pid])
    )
    pool = sorted(set(pool))

    sets, dropped = [], []
    for p in sorted(main_papers, key=lambda x: x["id"]):
        qid = p["id"]
        query = papers.get(qid)
        if query is None or not eligible(query) or not query["publication_date"]:
            dropped.append({"pi_id": qid, "reason": "query missing or without title/abstract/date"})
            continue

        cited = set(p["referenced_works"]) | set(query["referenced_works"])
        positives = [pid for pid in sorted(set(p["referenced_works"]))
                     if pid in papers and eligible(papers[pid])]
        if len(positives) < MIN_POSITIVES:
            dropped.append({"pi_id": qid, "reason": f"{len(positives)} eligible positives"})
            continue

        q_authors = set(query["author_ids"])
        candidates = [
            pid for pid in pool
            if pid not in cited and pid != qid
            and papers[pid]["publication_date"]
            and papers[pid]["publication_date"] < query["publication_date"]
            and not (q_authors & set(papers[pid]["author_ids"]))
        ]
        k = min(NEG_PER_POS * len(positives), len(candidates))
        picks = rng_for("negatives", qid, seed).choice(len(candidates), size=k, replace=False)
        negatives = [candidates[i] for i in sorted(picks)]

        sets.append({
            "pi_id": qid,
            "pi_title": query["title"],
            "pi_date": query["publication_date"],
            "positives": positives,
            "negatives": negatives,
            "n_ref_listed": len(set(p["referenced_works"])),
            "n_neg_pool": len(candidates),
        })

    used = {s["pi_id"] for s in sets} | {c for s in sets for c in s["positives"] + s["negatives"]}
    return {
        "seed": seed,
        "sets": sets,
        "dropped": dropped,
        "papers": {pid: papers[pid] for pid in sorted(used)},
    }


def assign_splits(sets: list[dict], seed: int = 0, dev_fraction: float = DEV_FRACTION) -> dict[str, str]:
    ordered = sorted(sets, key=lambda s: stable_seed("split", s["pi_id"], seed))
    n_dev = round(len(ordered) * dev_fraction)
    return {s["pi_id"]: ("dev" if i < n_dev else "test") for i, s in enumerate(ordered)}


def candidate_order(es: dict, mode: str, seed: int) -> list[str]:
    """Candidate ids in the order shown to a model.

    'original' reproduces v1 (positives first) and exists only for the
    position-bias experiment; real runs use 'shuffled'.
    """
    base = es["positives"] + es["negatives"]
    if mode == "original":
        return list(base)
    if mode == "reversed":
        return base[::-1]
    if mode == "shuffled":
        perm = rng_for("order", es["pi_id"], seed).permutation(len(base))
        return [base[i] for i in perm]
    raise ValueError(f"unknown order mode {mode!r}")


def _first_sentences(text: str, n: int) -> str:
    return " ".join(re.split(r"(?<=[.!?])\s+", text.strip())[:n])


def paper_text(rec: dict, fields: tuple[str, ...], max_chars: int | None = None,
               abstract_sentences: int | None = None) -> str:
    """The one text builder for queries and candidates in every method."""
    parts = []
    if "title" in fields and rec["title"]:
        parts.append(rec["title"])
    if "abstract" in fields and rec["abstract"]:
        abstract = rec["abstract"]
        parts.append(_first_sentences(abstract, abstract_sentences) if abstract_sentences else abstract)
    if "concepts" in fields and rec["concepts_array"]:
        parts.append("Concepts: " + ", ".join(rec["concepts_array"]))
    text = " ".join(parts)
    return text[:max_chars] if max_chars else text
