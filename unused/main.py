"""
Test runner for the OpenAlex client.
"""

from openalex_client import (
    find_institution,
    BOUN_OPENALEX_ID,
    sample_boun_works,
    work_to_text,
    authors_from_institution,
    works_from_institution,
)


def test_find_institution():
    print("=== find_institution ===")
    for query in ["Boğaziçi", "Stanford"]:
        results = find_institution(query, limit=3)
        print(f"\n  Search: {query!r}")
        for r in results:
            print(f"    - {r['display_name']} ({r['country_code']})  id={r['id']}")


def test_sample_boun_works():
    print("\n=== sample_boun_works ===")
    works = sample_boun_works(limit=5)
    print(f"  Fetched {len(works)} recent BOUN works:")
    for w in works:
        title = (w.get("title") or "")[:60]
        year = w.get("publication_year")
        print(f"    [{year}] {title}...")
    if works:
        text = work_to_text(works[0])
        print(f"\n  work_to_text(first): {text[:80]}...")


def test_authors_from_institution():
    print("\n=== authors_from_institution (first 3 BOUN authors) ===")
    boun_id = BOUN_OPENALEX_ID
    count = 0
    for page in authors_from_institution(boun_id, per_page=5):
        for author in page:
            print(f"    - {author.get('display_name')}  id={author.get('id')}")
            count += 1
            if count >= 3:
                break
        if count >= 3:
            break
    print(f"  (showed {count} authors)")


def test_works_from_institution_stream():
    print("\n=== works_from_institution (stream, first 2) ===")
    boun_id = BOUN_OPENALEX_ID
    count = 0
    for page in works_from_institution(boun_id, per_page=10):
        for work in page:
            title = (work.get("title") or "")[:50]
            year = work.get("publication_year")
            print(f"    [{year}] {title}...")
            count += 1
            if count >= 2:
                break
        if count >= 2:
            break
    print(f"  (streamed {count} works)")


if __name__ == "__main__":
    print("OpenAlex client tests\n")
    test_find_institution()
    test_sample_boun_works()
    test_authors_from_institution()
    test_works_from_institution_stream()
    print("\nDone.")
