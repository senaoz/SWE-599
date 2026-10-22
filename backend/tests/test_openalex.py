from backend.services.openalex import paper_from_work

# The fields the app reads, as OpenAlex returns them (W7135035213, trimmed).
WORK = {
    "id": "https://openalex.org/W7135035213",
    "doi": "https://doi.org/10.1098/rspa.2026.0073",
    "title": "Dynamics-informed deep learning for predicting extreme events",
    "abstract_inverted_index": {"Predicting": [0], "extreme": [1], "events.": [2]},
    "publication_date": "2026-10-21",
    "type": "article",
    "primary_topic": {
        "display_name": "Model Reduction and Neural Networks",
        "field": {"display_name": "Physics and Astronomy"},
    },
    "open_access": {"is_oa": True, "oa_url": "https://doi.org/10.1098/rspa.2026.0073"},
    "concepts": [{"display_name": "Deep learning"}],
}


def test_paper_from_work_keeps_type_field_and_links():
    p = paper_from_work(WORK, "MIT")
    assert p["openalex_id"] == WORK["id"]
    assert p["doi"] == "https://doi.org/10.1098/rspa.2026.0073"
    assert (p["type"], p["field"], p["oa_url"]) == ("article", "Physics and Astronomy", WORK["open_access"]["oa_url"])
    assert p["abstract"] == "Predicting extreme events."
    assert p["publication_date"].isoformat() == "2026-10-21"
    assert p["source_institution_name"] == "MIT"


def test_paper_from_work_tolerates_missing_parts():
    p = paper_from_work({"id": "https://openalex.org/W1"}, None)
    assert (p["type"], p["field"], p["oa_url"], p["abstract"], p["publication_date"]) == (None, None, None, None, None)
