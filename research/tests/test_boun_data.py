from src.boun_data import BOUN, boun_author_ids, build_clean, language_flag

ALWAYS_FALSE = {f: (lambda a: False) for f in
                ("author_list", "citation_string", "boilerplate", "title_like", "fragment",
                 "short_under_300", "availability_or_url")}


def test_language_flag():
    assert language_flag("Deep learning for the analysis of images", "We study the effect of noise on the results.") == "en"
    assert language_flag("Türkiye'de göç ve dil", "Bu çalışmada göçmenlerin dil kullanımı ile ilgili bulgular sunulmaktadır.") == "tr"
    assert language_flag("AVRUPA PATENT SİSTEMİ İÇİNDE", "The European Patent Convention went into force in 1977 and it is the basis of the system.") == "mixed"
    assert language_flag("Le féminisme en Turquie", "Le mouvement des femmes en Turquie et la modernité dans une société.") == "other"
    # "de"/"da" are Turkish too; Turkish letters keep a Turkish text out of "other".
    assert language_flag("Türkiye’de Deprem Oluş Düzenleri", "Depremler doğal olaylardır ve Türkiye'de de sıkça görülür.") == "tr"
    assert language_flag("", "") == "unknown"


def _authorship(aid, inst=None, lineage=(), raw=()):
    insts = [{"id": inst, "lineage": list(lineage)}] if inst else []
    return {"author": {"id": aid}, "institutions": insts, "raw_affiliation_strings": list(raw)}


def test_boun_author_ids_lineage_and_raw_fallback():
    w = {"authorships": [
        _authorship("A1", BOUN),
        _authorship("A2", "https://openalex.org/I999", lineage=[BOUN]),         # BOUN sub-unit
        _authorship("A3", raw=["Physics Department, Boğaziçi University, Istanbul"]),  # unresolved institution
        _authorship("A4", "https://openalex.org/I1", raw=["Bogazici University"]),     # resolved elsewhere: not BOUN
        _authorship(None, BOUN),                                                     # no author id
    ]}
    assert boun_author_ids(w) == ["A1", "A2", "A3"]


def _work(wid, title, date, typ="article", doi=None, abstract=None, author="A1"):
    return {"id": wid, "title": title, "publication_date": date, "publication_year": int(date[:4]), "type": typ,
            "doi": doi, "abstract_inverted_index": {w: [i] for i, w in enumerate(abstract.split())} if abstract else None,
            "authorships": [_authorship(author, BOUN)]}


def test_build_clean_merges_versions_and_keeps_external_text_apart():
    works = [
        _work("W1", "A long enough title about graph neural networks", "2021-03-01", "preprint", abstract="Preprint text here"),
        _work("W2", "A long enough title about graph neural networks", "2022-05-01", "article", doi="https://doi.org/10.1/x",
              author="A2"),
        _work("W3", "Correction to something", "2022-01-01", "erratum"),
        _work("W4", "Another work on climate", "2023-01-01", "article", doi="https://doi.org/10.1/y"),
    ]
    external = {"10.1/y": ("s2", "External abstract text")}
    rows, stats = build_clean(works, external, ALWAYS_FALSE)
    by_id = {r["id"]: r for r in rows}
    assert stats == {"fetched": 4, "research_types": 3, "after_dedup": 2, "merged_duplicates": 1, "suspect_large_works": 0}
    # The published version is canonical (W2 has no abstract of its own, so W1 is preferred as the
    # only member with text); either way the group keeps both authors and the earliest date.
    merged = by_id.get("W1") or by_id["W2"]
    assert sorted(merged["boun_author_ids"]) == ["A1", "A2"]
    assert merged["first_date"] == "2021-03-01"
    w4 = by_id["W4"]
    assert w4["abstract"] == "" and w4["abstract_external"] == "External abstract text"
    assert w4["abstract_source"] == "s2"


def test_names_boun_handles_encodings():
    from src.boun_data import names_boun
    assert names_boun("Bo&#x011F;azi&#x00E7;i University,Istanbul,Turkey")
    assert names_boun("Department of Mathematics, Bog̃aziçi University, İstanbul")
    assert names_boun("BOĞAZİÇİ ÜNİVERSİTESİ")
    assert names_boun("Bosphorus University, Istanbul")
    assert names_boun("Department of Computer Engineering , Bogazic ¸i University")
    assert not names_boun("Istanbul Technical University")


def test_suspect_large_collaboration_keeps_only_confirmed_authors():
    from src.boun_data import MAX_BOUN_AUTHORS_PER_LARGE_WORK
    n = MAX_BOUN_AUTHORS_PER_LARGE_WORK + 5
    big = {"id": "W1", "title": "A long collaboration paper on particle physics results", "publication_date": "2021-01-01",
           "publication_year": 2021, "type": "article", "doi": None, "abstract_inverted_index": None,
           "authorships": [_authorship(f"A{i}", BOUN) for i in range(n)] + [_authorship(f"X{i}") for i in range(100)]}
    small = _work("W2", "A small paper by one confirmed author", "2022-01-01", author="A3")
    rows, stats = build_clean([big, small], {}, ALWAYS_FALSE)
    by_id = {r["id"]: r for r in rows}
    assert stats["suspect_large_works"] == 1
    assert by_id["W1"]["boun_attribution_suspect"] and by_id["W1"]["boun_author_ids"] == ["A3"]
    assert not by_id["W2"]["boun_attribution_suspect"]
