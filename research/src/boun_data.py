"""BOUN works from the 2026-10 OpenAlex refetch: language flag, type filter, cleaning.

The OpenAlex `language` tag is not used: it marks English ATLAS papers as Latvian, for
example. Language is decided from the title and abstract by stopword counts.
"""
from __future__ import annotations

import re

TR_STOP = frozenset(
    "ve bir bu için ile olarak olan ise gibi daha çok en veya ancak üzerine ilişkin "
    "arasında sonra önce göre kadar olduğu olduğunu çalışma çalışmanın çalışmada araştırma "
    "araştırmanın amacı yöntem bulgular sonuç sonuçlar sonucunda tarafından üzerinde ilgili "
    "değerlendirilmesi incelenmesi etkisi türkiye'de bağlamında yönelik".split()
)
EN_STOP = frozenset(
    "the of and to in a is for on with that by as are from this an be we was were which "
    "these their at or has have results study using based between".split()
)
# Romance-language stopwords (these languages never use ı, ğ or ş); without them "de"/"la" texts fall into the Turkish or English bucket.
OTHER_STOP = frozenset(
    "de la le les des et du une un est dans pour que el los las y del por para con una em um uma "
    "do dos da das não com".split()
)
_TR_LETTERS = re.compile(r"[ığşİĞŞ]")
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.U)


def language_flag(title: str | None, abstract: str | None) -> str:
    """'en', 'tr', 'mixed' (Turkish title with English abstract or the reverse), 'other' or 'unknown'."""

    def lang(text: str | None) -> str:
        words = _WORD.findall((text or "").lower())
        tr = sum(w in TR_STOP for w in words)
        en = sum(w in EN_STOP for w in words)
        other = sum(w in OTHER_STOP for w in words)
        if other > max(tr, en) and not _TR_LETTERS.search(text or ""):
            return "other"
        if tr == en == 0:
            # Short or all-caps titles often have no stopwords; fall back to letters only Turkish uses.
            return "tr" if len(_TR_LETTERS.findall(text or "")) >= 2 else "unknown"
        return "tr" if tr > en else "en"

    t, a = lang(title), lang(abstract)
    if a == "unknown":
        return t
    if t in ("unknown", a):
        return a
    if {t, a} == {"en", "tr"}:
        return "mixed"
    return a if t == "other" else "other"  # a short title is weaker evidence than the abstract


# Research outputs that can describe a researcher's work. Excluded: corrections and notices
# (erratum, retraction), commentary (editorial, letter, peer-review, book-review), paratext,
# and non-paper outputs (dataset, software, supplementary-materials, other).
RESEARCH_TYPES = frozenset({
    "article", "conference-paper", "review", "preprint", "book-chapter", "book",
    "conference-abstract", "dissertation", "report", "data-paper", "reference-entry",
})


BOUN = "https://openalex.org/I4405392"
STRONG_FLAGS = ("author_list", "citation_string", "boilerplate", "title_like", "fragment")
WEAK_FLAGS = ("short_under_300", "availability_or_url")


_BOUN_RAW = re.compile(r"bo[gğ]azi[cç]i|bosphorus univ|bogazici", re.I)


def boun_author_ids(w: dict) -> list[str]:
    """Authors with a BOUN affiliation on this work: institution id or lineage, or, when OpenAlex
    resolved no institution, a raw affiliation string naming Boğaziçi University."""
    out = set()
    for a in w.get("authorships") or []:
        aid = (a.get("author") or {}).get("id")
        insts = a.get("institutions") or []
        if aid and (any(BOUN == i.get("id") or BOUN in (i.get("lineage") or []) for i in insts)
                    or (not insts and any(_BOUN_RAW.search(r) for r in a.get("raw_affiliation_strings") or []))):
            out.add(aid)
    return sorted(out)


def build_clean(works: list[dict], external: dict[str, tuple[str, str]], dq_flags: dict,
                full_authors: dict[str, list[str]] | None = None) -> tuple[list[dict], dict]:
    """Clean BOUN works: research types only, duplicates merged, language and quality flags.

    external: {normalized doi: (source, abstract)} from Crossref / Semantic Scholar.
    dq_flags: {flag name: predicate on an abstract} (research/audit/data_quality.py).
    full_authors: {work id: BOUN author ids} from single-work calls, for records whose
    list-endpoint author list was cut at 100.
    Rows keep only OpenAlex abstracts in `abstract`; external text goes to `abstract_external`,
    which callers must drop before writing anything that is pushed.
    """
    import html
    from src.cograph import canonical_map, norm_doi
    from src.text_utils import clean_abstract, reconstruct_abstract

    stats = {"fetched": len(works)}
    works = [w for w in works if w["type"] in RESEARCH_TYPES]
    stats["research_types"] = len(works)
    recs = {}
    for w in works:
        ab = clean_abstract(reconstruct_abstract(w.get("abstract_inverted_index"))) or ""
        ext_src, ext_ab = external.get(norm_doi(w.get("doi")), ("", ""))
        recs[w["id"]] = {
            "id": w["id"], "doi": norm_doi(w.get("doi")), "title": html.unescape(w.get("title") or "").strip(),
            "abstract": ab, "abstract_external": "" if ab or not ext_ab else (clean_abstract(ext_ab) or ""),
            "publication_date": w.get("publication_date") or "", "publication_year": w.get("publication_year"),
            "year_only_date": (w.get("publication_date") or "").endswith("-01-01"),
            "type": w["type"], "language_openalex": w.get("language") or "",
            "primary_topic": ((w.get("primary_topic") or {}).get("display_name") or ""),
            "topics": [t["display_name"] for t in w.get("topics") or []],
            "keywords": [k["display_name"] for k in w.get("keywords") or []],
            "concepts": [c["display_name"] for c in w.get("concepts") or [] if c.get("display_name")],
            "boun_author_ids": (full_authors or {}).get(w["id"], boun_author_ids(w)),
            "author_ids": sorted({(a.get("author") or {}).get("id") for a in w.get("authorships") or []} - {None}),
            "referenced_works_count": w.get("referenced_works_count") or 0,
            "cited_by_count": w.get("cited_by_count") or 0,
            "is_retracted": bool(w.get("is_retracted")),
            "authors_truncated": len(w.get("authorships") or []) >= 100 and w["id"] not in (full_authors or {}),
            "large_collaboration": len(w.get("authorships") or []) >= 100,  # 100+ authors (e.g. ATLAS, CMS)
        }
        r = recs[w["id"]]
        r["abstract_source"] = "openalex" if ab else (ext_src if r["abstract_external"] else "none")
        r["language_flag"] = language_flag(r["title"], ab or r["abstract_external"])

    # Duplicates: prefer a non-preprint record with an abstract as the canonical one.
    prefer = {i for i, r in recs.items() if r["type"] != "preprint" and (r["abstract"] or r["abstract_external"])}
    canon = canonical_map({i: {**r, "abstract": r["abstract"] or r["abstract_external"]} for i, r in recs.items()}, prefer)
    groups: dict[str, list[str]] = {}
    for i, c in canon.items():
        groups.setdefault(c, []).append(i)
    out = []
    for c, members in groups.items():
        row = dict(recs[c])
        others = [recs[m] for m in sorted(members) if m != c]
        row["duplicate_ids"] = [o["id"] for o in others]
        # Earliest date in the group: a preprint makes the work's content known before publication.
        row["first_date"] = min([row["publication_date"]] + [o["publication_date"] for o in others if o["publication_date"]])
        row["boun_author_ids"] = sorted(set(row["boun_author_ids"]).union(*[o["boun_author_ids"] for o in others]))
        if not row["abstract"] and not row["abstract_external"]:
            donor = next((o for o in others if o["abstract"] or o["abstract_external"]), None)
            if donor:
                row["abstract"], row["abstract_external"] = donor["abstract"], donor["abstract_external"]
                row["abstract_source"] = donor["abstract_source"] + "_duplicate"
        text = row["abstract"] or row["abstract_external"]
        row["dq_strong"] = [f for f in STRONG_FLAGS if text and dq_flags[f](text)]
        row["dq_weak"] = [f for f in WEAK_FLAGS if text and dq_flags[f](text)]
        out.append(row)
    stats["after_dedup"] = len(out)
    stats["merged_duplicates"] = stats["research_types"] - len(out)
    return sorted(out, key=lambda r: r["id"]), stats
