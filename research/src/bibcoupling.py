"""Bibliographic coupling and direct citation as researcher-paper match signals.

Used on the Stelmakh et al. gold standard (research/v2/14_bibcoupling_goldstandard.ipynb).
Every paper is a set of reference ids in one id space (never mix OpenAlex and Semantic
Scholar ids in one score). Three signals are kept apart because they have different confounds:

    coupling          the rated paper and a profile paper cite the same works (under test)
    forward citation  the rated paper cites a profile paper (the app case: an external paper
                      cites a researcher's work)
    reverse citation  a profile paper cites the rated paper (a selection artefact: participants
                      rated papers they had read, and may have cited them)

The loss is the weighted Kendall-tau of Stelmakh et al. (scripts/scoring.py in their
repository, MIT), ported here so no code from the downloaded data is executed.
"""
from __future__ import annotations

import math
from itertools import combinations

import numpy as np

COUPLING_KINDS = ("overlap", "jaccard", "cosine", "idf_cosine")
AGGREGATIONS = ("max", "mean", "top3")


# ---------------------------------------------------------------------------
# Pair signals
# ---------------------------------------------------------------------------

def idf_weights(counts: dict[str, int], n_docs: int) -> dict[str, float]:
    """IDF weight per referenced work: log((n_docs + 1) / (count + 1)), floored at 0.

    counts: how many documents cite each work (local document frequency, or a global
    citation count with n_docs the size of the citing population).
    """
    return {w: max(0.0, math.log((n_docs + 1) / (c + 1))) for w, c in counts.items()}


def coupling(a: set[str], b: set[str], kind: str = "idf_cosine",
             idf: dict[str, float] | None = None) -> float:
    """Similarity of two reference sets. Empty sets score 0.

    overlap     |A & B|
    jaccard     |A & B| / |A | B|
    cosine      |A & B| / sqrt(|A| |B|)
    idf_cosine  cosine of binary vectors weighted by idf (a work missing from idf weighs 0)
    """
    if not a or not b:
        return 0.0
    shared = a & b
    if kind == "overlap":
        return float(len(shared))
    if kind == "jaccard":
        return len(shared) / len(a | b)
    if kind == "cosine":
        return len(shared) / math.sqrt(len(a) * len(b))
    if kind == "idf_cosine":
        if idf is None:
            raise ValueError("idf_cosine needs idf weights")
        sq = lambda s: sum(idf.get(w, 0.0) ** 2 for w in s)
        na, nb = sq(a), sq(b)
        return sq(shared) / math.sqrt(na * nb) if na and nb else 0.0
    raise ValueError(f"unknown coupling kind: {kind}")


def cites(citing_refs: set[str], cited_ids: set[str]) -> bool:
    """True if a paper's reference list contains any id of the cited paper.

    cited_ids holds every record a paper maps to (e.g. its DOI and arXiv records), so a
    citation of the preprint version still counts.
    """
    return bool(citing_refs & cited_ids)


def forward_citation(rated_refs: set[str], profile_ids: list[set[str]]) -> int:
    """Number of profile papers the rated paper cites."""
    return sum(cites(rated_refs, ids) for ids in profile_ids)


def reverse_citation(profile_refs: list[set[str]], rated_ids: set[str]) -> int:
    """Number of profile papers that cite the rated paper (selection artefact; report apart)."""
    return sum(cites(refs, rated_ids) for refs in profile_refs)


# ---------------------------------------------------------------------------
# Aggregation over profile papers
# ---------------------------------------------------------------------------

def aggregate(scores, how: str = "max") -> float:
    """max (what the app uses), mean, or top3 (mean of the top min(3, n)). Empty -> 0."""
    s = sorted(scores, reverse=True)
    if not s:
        return 0.0
    if how == "max":
        return float(s[0])
    if how == "mean":
        return float(np.mean(s))
    if how == "top3":
        return float(np.mean(s[:3]))
    raise ValueError(f"unknown aggregation: {how}")


# ---------------------------------------------------------------------------
# Metric (weighted Kendall-tau loss, Stelmakh et al.)
# ---------------------------------------------------------------------------

def _pair_losses(pred: dict[str, float], ref: dict[str, float], keep=None) -> tuple[float, float]:
    loss = max_loss = 0.0
    for p1, p2 in combinations(sorted(ref), 2):
        if keep is not None and not keep(p1, p2):
            continue
        pd_, td = pred[p1] - pred[p2], ref[p1] - ref[p2]
        max_loss += abs(td)
        if pd_ * td == 0:
            loss += abs(td) / 2
        elif pd_ * td < 0:
            loss += abs(td)
    return loss, max_loss


def kt_loss(preds: dict, refs: dict, reviewers=None) -> float:
    """Official pooled loss: total loss / total maximal loss over the given reviewers.

    reviewers may repeat (bootstrap samples). Ties in the prediction cost half.
    """
    loss = max_loss = 0.0
    for r in (refs if reviewers is None else reviewers):
        l, m = _pair_losses(preds[r], refs[r])
        loss += l
        max_loss += m
    return loss / max_loss


def kt_loss_pairs(preds: dict, refs: dict, keep) -> tuple[float, int]:
    """Pooled loss over the rated-paper pairs where keep(reviewer, p1, p2) holds.

    Returns (loss, number of pairs with different true scores); loss is nan if there are none.
    """
    loss = max_loss = 0.0
    n = 0
    for r in refs:
        l, m = _pair_losses(preds[r], refs[r], lambda a, b: keep(r, a, b))
        loss += l
        max_loss += m
        n += sum(1 for a, b in combinations(sorted(refs[r]), 2)
                 if keep(r, a, b) and refs[r][a] != refs[r][b])
    return (loss / max_loss if max_loss else float("nan")), n


def per_reviewer_loss(preds: dict, refs: dict) -> dict[str, float]:
    """Each reviewer's own loss (for paired tests). Reviewers with all-equal labels are skipped."""
    out = {}
    for r in refs:
        l, m = _pair_losses(preds[r], refs[r])
        if m > 0:
            out[r] = l / m
    return out


def _reviewer_table(preds: dict, refs: dict) -> dict[str, tuple[float, float]]:
    return {r: _pair_losses(preds[r], refs[r]) for r in refs}


def _pooled(table: dict, reviewers) -> float:
    loss = sum(table[r][0] for r in reviewers)
    return loss / sum(table[r][1] for r in reviewers)


def bootstrap_ci(preds_by_sample: list[dict], refs: dict, n_boot: int = 1000,
                 seed: int = 0) -> tuple[float, float, float]:
    """Official protocol with a fixed seed: mean pooled loss over profile samples, and a 95% CI
    from resampling reviewers (the same pools for every sample, averaged over samples).
    The same seed gives the same pools for every method, so CIs are comparable."""
    rng = np.random.default_rng(seed)
    reviewers = sorted(refs)
    pools = [rng.choice(reviewers, len(reviewers), replace=True) for _ in range(n_boot)]
    tables = [_reviewer_table(p, refs) for p in preds_by_sample]
    point = float(np.mean([_pooled(t, reviewers) for t in tables]))
    boot = np.mean([[_pooled(t, pool) for pool in pools] for t in tables], axis=0)
    return point, float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


# ---------------------------------------------------------------------------
# Fusion with an embedding score
# ---------------------------------------------------------------------------

def zscore_within(preds: dict) -> dict:
    """z-score each reviewer's scores over their rated papers; constant scores become 0."""
    out = {}
    for r, d in preds.items():
        v = np.array(list(d.values()), dtype=float)
        sd = v.std()
        out[r] = {p: (s - v.mean()) / sd if sd > 0 else 0.0 for p, s in d.items()}
    return out


def fuse_linear(a: dict, b: dict, alpha: float) -> dict:
    """alpha * z(a) + (1 - alpha) * z(b), per reviewer."""
    za, zb = zscore_within(a), zscore_within(b)
    return {r: {p: alpha * za[r][p] + (1 - alpha) * zb[r][p] for p in za[r]} for r in za}


def _ranks(d: dict) -> dict:
    """Rank 1 = best; ties share their mean rank, so tied coupling scores add no order."""
    keys = list(d)
    v = np.array([d[k] for k in keys], dtype=float)
    order = (-v).argsort(kind="stable")
    ranks = np.empty(len(v))
    ranks[order] = np.arange(1, len(v) + 1)
    for val in set(v):
        idx = v == val
        ranks[idx] = ranks[idx].mean()
    return dict(zip(keys, ranks))


def fuse_rrf(a: dict, b: dict, k: float) -> dict:
    """Reciprocal rank fusion per reviewer: 1/(k + rank_a) + 1/(k + rank_b)."""
    out = {}
    for r in a:
        ra, rb = _ranks(a[r]), _ranks(b[r])
        out[r] = {p: 1 / (k + ra[p]) + 1 / (k + rb[p]) for p in ra}
    return out


def lopo_select(score_fn, grid, refs: dict) -> tuple[dict, dict]:
    """Leave-one-participant-out choice of a fusion parameter.

    score_fn(param) -> list of preds dicts (one per profile sample). For each held-out
    reviewer, the parameter minimizing the mean pooled loss over the other reviewers is
    chosen and that reviewer's predictions come from it. Returns (preds per sample, choice
    per reviewer); only these held-out predictions may be reported.
    """
    by_param = {g: score_fn(g) for g in grid}
    tables = {g: [_reviewer_table(p, refs) for p in by_param[g]] for g in grid}
    reviewers = sorted(refs)
    choice = {}
    for held in reviewers:
        rest = [r for r in reviewers if r != held]
        losses = {g: np.mean([_pooled(t, rest) for t in tables[g]]) for g in grid}
        choice[held] = min(grid, key=lambda g: (losses[g], grid.index(g)))
    n_samples = len(by_param[grid[0]])
    preds = [{r: by_param[choice[r]][i][r] for r in reviewers} for i in range(n_samples)]
    return preds, choice
