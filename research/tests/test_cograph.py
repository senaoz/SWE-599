"""Unit tests for the Phase 5 leakage rules and canonicalization (src/cograph.py).

Synthetic graph. Query Q (2020-06-01) cites positives P1 and P2. Candidate docs: P1, P2, N.

    citer       date        cites        role
    Q           2020-06-01  P1, P2       the query itself (R1/R2)
    Q_PRE       2019-01-01  P1, P2       earlier version of Q, same title (R3)
    OTHERQ      2020-01-01  P1, P2       another query record (R5)
    LATE        2020-06-01  P1, P2       published the same day as Q (R4 boundary)
    FUTURE      2021-01-01  P1, P2       published after Q (R4)
    OK          2020-05-31  P1, N        a legitimate earlier citer
"""
import numpy as np
import pytest

from src.cograph import Rules, build_graph, canonical_map, curveball, query_duplicates

DOCS = ["P1", "P2", "N"]
CITERS = {
    "Q": {"publication_date": "2020-06-01", "referenced_works": ["P1", "P2"], "title": "A study of things in depth today"},
    "Q_PRE": {"publication_date": "2019-01-01", "referenced_works": ["P1", "P2"], "title": "A Study of Things in Depth Today"},
    "OTHERQ": {"publication_date": "2020-01-01", "referenced_works": ["P1", "P2"], "title": "Another query paper with title"},
    "LATE": {"publication_date": "2020-06-01", "referenced_works": ["P1", "P2"], "title": "Same day paper about some topic"},
    "FUTURE": {"publication_date": "2021-01-01", "referenced_works": ["P1", "P2"], "title": "A later paper about some topic"},
    "OK": {"publication_date": "2020-05-31", "referenced_works": ["P1", "N"], "title": "An earlier paper about some topic"},
}
QUERIES = {q: CITERS[q] for q in ("Q", "OTHERQ")}


@pytest.fixture
def graph():
    dups = query_duplicates({c: v for c, v in CITERS.items() if c not in QUERIES}, QUERIES)
    return build_graph(CITERS, DOCS, {d: d for d in DOCS}, set(QUERIES), set(dups))


def allowed_ids(g, rules=Rules()):
    mask = g.allowed("Q", "2020-06-01", rules)
    return {c for c, m in zip(g.citer_ids, mask) if m}


def p2_cocited_with_p1(g, rules=Rules()):
    idx = g.doc_index
    return g.cocitation([idx["P1"]], g.allowed("Q", "2020-06-01", rules))[idx["P2"]]


def test_all_rules_leave_only_the_legitimate_citer(graph):
    assert allowed_ids(graph) == {"OK"}
    assert p2_cocited_with_p1(graph) == 0  # P2 is not reachable from P1 without leakage


def test_r1_r2_query_row_never_used_and_canary_adds_it(graph):
    assert "Q" not in allowed_ids(graph, Rules(temporal=False, drop_query_dups=False, drop_query_records=False))
    assert "Q" in allowed_ids(graph, Rules(canary=True))
    assert p2_cocited_with_p1(graph, Rules(canary=True)) == 1


def test_r3_same_title_earlier_version_is_a_duplicate(graph):
    dups = query_duplicates({c: v for c, v in CITERS.items() if c not in QUERIES}, QUERIES)
    assert dups == {"Q_PRE": ("Q", "title")}
    assert "Q_PRE" in allowed_ids(graph, Rules(drop_query_dups=False))
    assert p2_cocited_with_p1(graph, Rules(drop_query_dups=False)) == 1


def test_r3_doi_and_near_title_duplicates():
    by = lambda *ids: [{"author": {"id": i}} for i in ids]  # noqa: E731
    queries = {"Q": {"doi": "https://doi.org/10.1/ABC", "title": "Strengthening the reporting of cohort studies in surgery 2024",
                     "authorships": by("A1", "A2")}}
    citers = {"D": {"doi": "10.1/abc", "title": "Unrelated"},
              "T": {"doi": None, "title": "Strengthening the reporting of cohort studies in surgery 2021", "authorships": by("A2")},
              "U": {"doi": None, "title": "Strengthening the reporting of cohort studies in surgery 2019", "authorships": by("A9")},
              "X": {"doi": None, "title": "Reporting of trials in surgery", "authorships": by("A1")}}
    # near-title needs a shared author (U has none); an exact title does not (see the module docstring)
    assert query_duplicates(citers, queries) == {"D": ("Q", "doi"), "T": ("Q", "near-title")}


def test_r3_near_title_rejects_different_papers_with_similar_words():
    by = [{"author": {"id": "A1"}}]
    queries = {"Q": {"title": "Airborne Transmission of SARS-CoV-2 in hospitals", "authorships": by}}
    citers = {"A": {"title": "On airborne transmission and control of SARS-CoV-2 in hospitals", "authorships": by}}
    assert query_duplicates(citers, queries) == {}


def test_r4_temporal_is_strict(graph):
    ids = allowed_ids(graph, Rules(drop_query_dups=False, drop_query_records=False))
    assert "LATE" not in ids and "FUTURE" not in ids  # same day and later are both excluded
    assert {"OK", "Q_PRE", "OTHERQ"} <= ids
    assert {"LATE", "FUTURE"} <= allowed_ids(graph, Rules(temporal=False))


def test_r5_other_query_records_excluded(graph):
    assert "OTHERQ" not in allowed_ids(graph)
    assert "OTHERQ" in allowed_ids(graph, Rules(drop_query_records=False))


def test_missing_date_is_never_before_the_query():
    citers = {"U": {"publication_date": None, "referenced_works": ["P1", "P2"]}}
    g = build_graph(citers, DOCS, {d: d for d in DOCS}, set(), set())
    assert not g.allowed("Q", "2020-06-01").any()


def test_references_are_canonicalized_and_outside_docs_dropped():
    citers = {"C": {"publication_date": "2019-01-01", "referenced_works": ["P1_DUP", "P2", "ELSEWHERE"]}}
    g = build_graph(citers, DOCS, {"P1_DUP": "P1"}, set(), set())
    assert g.C.toarray().tolist() == [[1.0, 1.0, 0.0]]


def test_canonical_map():
    recs = {
        "W1": {"title": "Why most published research findings are false", "publication_date": "2005-08-30", "abstract": "x"},
        "W2": {"title": "Why Most Published Research Findings Are False.", "publication_date": "2005-01-01", "abstract": ""},
        "W3": {"title": "Why most published research findings are false", "publication_date": "2015-01-01", "abstract": "x"},
        "W4": {"title": "Editorial", "publication_date": "2020-01-01"},
        "W5": {"title": "Editorial", "publication_date": "2020-01-01"},
        "W6": {"title": "Something else entirely here", "doi": "https://doi.org/10.5/X", "publication_date": "2019-01-01"},
        "W7": {"title": "A preprint title differs a lot", "doi": "10.5/x", "publication_date": "2018-01-01"},
    }
    canon = canonical_map(recs, prefer={"W2"})
    assert canon["W1"] == canon["W2"] == "W2"    # same title, same year; the preferred id wins
    assert canon["W3"] == "W3"                   # same title but 10 years apart: not merged
    assert canon["W4"] == "W4" and canon["W5"] == "W5"  # short titles never merge on title
    assert canon["W6"] == canon["W7"]            # same DOI


def test_curveball_preserves_degrees_and_leaves_other_rows():
    rng = np.random.default_rng(0)
    citers = {f"C{i}": {"publication_date": "2019-01-01",
                        "referenced_works": list(rng.choice(DOCS + ["D4", "D5", "D6"], size=3, replace=False))}
              for i in range(30)}
    citers["QROW"] = {"publication_date": "2019-01-01", "referenced_works": ["P1", "P2"]}
    docs = DOCS + ["D4", "D5", "D6"]
    g = build_graph(citers, docs, {d: d for d in docs}, {"QROW"}, set())
    pool = np.flatnonzero(~g.is_query)
    r = curveball(g, pool, np.random.default_rng(1))
    assert (np.asarray(r.C.sum(1)).ravel() == np.asarray(g.C.sum(1)).ravel()).all()
    assert (np.asarray(r.C[pool].sum(0)).ravel() == np.asarray(g.C[pool].sum(0)).ravel()).all()
    q = g.row_of("QROW")
    assert (r.C[q].toarray() == g.C[q].toarray()).all()
    assert (r.C != g.C).nnz > 0   # something actually moved
