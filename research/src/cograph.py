"""Phase 5: record canonicalization and the leakage-controlled co-citation graph.

The graph is a sparse citer x document incidence matrix over the candidate corpus.
Every citer row keeps its publication date and its kind, so each leakage rule
(research/audit/IMPROVEMENT_IDEAS.md, Idea C; PHASE5_DESIGN.md) is a mask over rows, applied per query:

    R1/R2  the query's own row (its reference list) is never a citer
    R3     rows that duplicate any query record (same DOI, same title, near-same title,
           including earlier versions of living reviews) are dropped
    R4     only citers published strictly before the query
    R5     no query record is a citer

`Rules` switches each rule off for the ablations; `canary=True` adds the query's own
row on purpose, which must make its positives reachable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import numpy as np
import scipy.sparse as sp

MIN_TITLE_WORDS = 5     # shorter titles ("Editorial", "NeRF") never merge on title alone
NEAR_TITLE_RATIO = 0.9  # character similarity of digit-free titles (catches "STROCSS 2021" vs "2024")
_STOP = {"a", "an", "and", "the", "of", "in", "on", "for", "to", "with", "by", "from", "at", "or", "as", "is"}


def norm_title(title: str | None) -> str:
    return re.sub(r"\W+", " ", (title or "").lower()).strip()


def title_tokens(title: str | None) -> frozenset[str]:
    return frozenset(t for t in norm_title(title).split() if t not in _STOP)


def undated_title(title: str | None) -> str:
    """Normalized title without numbers, so yearly editions of one document compare equal."""
    return " ".join(t for t in norm_title(title).split() if not t.isdigit())


def author_ids(rec: dict) -> set[str]:
    return {(a.get("author") or {}).get("id") for a in rec.get("authorships") or []} - {None}


def norm_doi(doi: str | None) -> str:
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", (doi or "").strip().lower())


# ---------------------------------------------------------------------------
# Canonicalization
# ---------------------------------------------------------------------------

def canonical_map(records: dict[str, dict], prefer: set[str] = frozenset()) -> dict[str, str]:
    """Map every record id to one canonical id per duplicate group.

    Duplicates: the same DOI, or the same normalized title (at least MIN_TITLE_WORDS words)
    with publication years at most one apart. The canonical id is a preferred id (e.g. a
    positive) if the group has one, else the record with an abstract, else the smallest id.
    records: {id: {"title", "doi", "publication_date", "abstract"}}.
    """
    parent = {i: i for i in records}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_doi: dict[str, str] = {}
    by_title: dict[str, list[str]] = {}
    for i in sorted(records):
        rec = records[i]
        d = norm_doi(rec.get("doi"))
        if d:
            if d in by_doi:
                union(by_doi[d], i)
            else:
                by_doi[d] = i
        t = norm_title(rec.get("title"))
        if len(t.split()) >= MIN_TITLE_WORDS:
            by_title.setdefault(t, []).append(i)
    for ids in by_title.values():
        for a_i, a in enumerate(ids):
            ya = _year(records[a])
            for b in ids[a_i + 1:]:
                yb = _year(records[b])
                if ya is not None and yb is not None and abs(ya - yb) <= 1:
                    union(a, b)

    groups: dict[str, list[str]] = {}
    for i in records:
        groups.setdefault(find(i), []).append(i)
    out = {}
    for members in groups.values():
        canon = min(members, key=lambda i: (i not in prefer, not records[i].get("abstract"), i))
        out.update({i: canon for i in members})
    return out


def _year(rec: dict) -> int | None:
    d = rec.get("publication_date") or ""
    return int(d[:4]) if d[:4].isdigit() else None


def query_duplicates(citers: dict[str, dict], queries: dict[str, dict]) -> dict[str, tuple[str, str]]:
    """Citers that duplicate a query record: {citer id: (query id, reason)}.

    Reasons: 'doi'; 'title' (same normalized title, any year: this also catches earlier
    versions of living reviews, whose author ids OpenAlex does not always link);
    'near-title' (character similarity >= NEAR_TITLE_RATIO between digit-free titles of at
    least MIN_TITLE_WORDS words, plus at least one shared author id, e.g. yearly editions
    of a guideline). Without the author condition, near-titles matched unrelated papers
    such as "Addressing the social determinants of health" (2010) for a 2020 query.
    """
    from difflib import SequenceMatcher

    q_doi = {norm_doi(q.get("doi")): qid for qid, q in queries.items() if norm_doi(q.get("doi"))}
    q_title = {norm_title(q.get("title")): qid for qid, q in queries.items() if norm_title(q.get("title"))}
    q_near = {qid: (undated_title(q.get("title")), title_tokens(q.get("title")), author_ids(q))
              for qid, q in queries.items() if len(undated_title(q.get("title")).split()) >= MIN_TITLE_WORDS}
    out = {}
    for cid, c in citers.items():
        if cid in queries:
            continue
        d = norm_doi(c.get("doi"))
        if d and d in q_doi:
            out[cid] = (q_doi[d], "doi")
            continue
        t = norm_title(c.get("title"))
        if t and t in q_title:
            out[cid] = (q_title[t], "title")
            continue
        ct = undated_title(c.get("title"))
        if len(ct.split()) < MIN_TITLE_WORDS:
            continue
        ctok, cauth = title_tokens(c.get("title")), author_ids(c)
        for qid, (qt, qtok, qauth) in q_near.items():
            if not cauth & qauth or len(ctok & qtok) * 2 < len(ctok | qtok):  # prefilter: Jaccard < 0.5
                continue
            if SequenceMatcher(None, ct, qt).ratio() >= NEAR_TITLE_RATIO:
                out[cid] = (qid, "near-title")
                break
    return out


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

NO_DATE = np.iinfo(np.int32).max  # a citer without a date is never "before" a query


def day(d: str | None) -> int:
    return date.fromisoformat(d).toordinal() if d else NO_DATE


@dataclass
class Rules:
    temporal: bool = True             # R4
    drop_query_dups: bool = True      # R3
    drop_query_records: bool = True   # R5
    canary: bool = False              # add the query's own reference list on purpose (R1/R2 off)


@dataclass
class CoGraph:
    C: sp.csr_matrix          # citers x docs, 1 if the citer cites the doc
    doc_ids: list[str]
    citer_ids: list[str]
    citer_day: np.ndarray     # ordinal publication day (NO_DATE if unknown)
    is_query: np.ndarray      # row is a query record
    is_query_dup: np.ndarray  # row duplicates some query record (R3)

    @property
    def doc_index(self) -> dict[str, int]:
        return {d: i for i, d in enumerate(self.doc_ids)}

    def row_of(self, citer_id: str) -> int | None:
        if not hasattr(self, "_rows"):
            self._rows = {c: i for i, c in enumerate(self.citer_ids)}
        return self._rows.get(citer_id)

    def allowed(self, qid: str, qdate: str, rules: Rules = Rules()) -> np.ndarray:
        """Boolean mask of citer rows usable for query `qid` under `rules`."""
        mask = np.ones(len(self.citer_ids), dtype=bool)
        if rules.temporal:
            mask &= self.citer_day < day(qdate)
        if rules.drop_query_dups:
            mask &= ~self.is_query_dup
        if rules.drop_query_records:
            mask &= ~self.is_query
        own = self.row_of(qid)
        if own is not None:
            mask[own] = rules.canary   # R1/R2: never the query itself, unless the canary asks for it
        return mask

    def cocitation(self, seeds: list[int], mask: np.ndarray, weights=None) -> np.ndarray:
        """Co-citation score of every doc with the seed docs, counted over allowed citers.

        score(d) = sum over allowed citers c of [c cites d] * sum_s w_s [c cites s]
        """
        w = np.ones(len(seeds)) if weights is None else np.asarray(weights, dtype=float)
        per_citer = self.C[:, seeds] @ w
        per_citer = np.where(mask, per_citer, 0.0)
        return np.asarray(self.C.T @ per_citer).ravel()

    def degree(self, mask: np.ndarray) -> np.ndarray:
        """Number of allowed citers citing each doc."""
        return np.asarray(self.C[mask].sum(axis=0)).ravel()


def build_graph(citers: dict[str, dict], doc_ids: list[str], canon: dict[str, str],
                query_ids: set[str], query_dups: set[str]) -> CoGraph:
    """citers: {id: {"publication_date", "referenced_works"}}, including query records.
    References are mapped to canonical ids; references outside the corpus are dropped."""
    index = {d: i for i, d in enumerate(doc_ids)}
    citer_ids = sorted(citers)
    rows, cols = [], []
    for r, cid in enumerate(citer_ids):
        cols_r = {index[canon.get(ref, ref)] for ref in citers[cid].get("referenced_works") or []
                  if canon.get(ref, ref) in index}
        rows.extend([r] * len(cols_r))
        cols.extend(sorted(cols_r))
    C = sp.csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)),
                      shape=(len(citer_ids), len(doc_ids)))
    return CoGraph(
        C=C, doc_ids=list(doc_ids), citer_ids=citer_ids,
        citer_day=np.array([day(citers[c].get("publication_date")) for c in citer_ids], dtype=np.int64),
        is_query=np.array([c in query_ids for c in citer_ids]),
        is_query_dup=np.array([c in query_dups for c in citer_ids]),
    )


def curveball(g: CoGraph, rows: np.ndarray, rng: np.random.Generator, n_trades: int | None = None) -> CoGraph:
    """Degree-preserving random rewiring (Curveball, Strona et al. 2014) of the given rows.

    Each trade picks two rows and reshuffles the docs only one of them cites, so every row
    keeps its number of citations and every doc keeps its number of citers within `rows`.
    Rows outside `rows` (query records, duplicates) are left untouched, so their edges can
    never move into the rewired pool.
    """
    rows = np.asarray(rows)
    sets = {int(r): set(g.C.indices[g.C.indptr[r]:g.C.indptr[r + 1]].tolist()) for r in rows}
    n_trades = n_trades if n_trades is not None else 5 * len(rows)
    for _ in range(n_trades):
        a, b = rng.choice(rows, size=2, replace=False)
        sa, sb = sets[int(a)], sets[int(b)]
        only_a, only_b = sa - sb, sb - sa
        if not only_a and not only_b:
            continue
        pool = list(only_a | only_b)
        rng.shuffle(pool)
        new_a = set(pool[:len(only_a)])
        sets[int(a)] = (sa & sb) | new_a
        sets[int(b)] = (sa & sb) | (set(pool) - new_a)
    C = g.C.tolil(copy=True)
    for r, cols in sets.items():
        C.rows[r] = sorted(cols)
        C.data[r] = [1.0] * len(cols)
    return CoGraph(C=C.tocsr(), doc_ids=g.doc_ids, citer_ids=g.citer_ids, citer_day=g.citer_day,
                   is_query=g.is_query, is_query_dup=g.is_query_dup)
