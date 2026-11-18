from lore_sync.verify import (
    build_report,
    compare_file,
    page_link_targets,
    source_matches_file,
    source_stats,
)

META = {"id": "idA", "name": "Lore - Personen", "mimeType": "application/vnd.google-apps.document"}

PAGES = [
    {
        "title": "Anna",
        "content": "Woont in [[Ventium]].",
        "infoboxRows": [{"cells": ["Naam", "Anna"]}],
        "sources": ["Lore - Personen (idA)"],
    },
    {"title": "Zonder bron", "content": "", "infoboxRows": [], "sources": []},
]


def test_source_stats_counts_links_and_sections():
    text = "Naam: Anna\nInfo: {Ventium} en {?}\n\nNaam: Bert\nInfo: {-} x\nfoto.jpg\n"
    stats = source_stats(text)
    assert stats["link_refs"] == 1
    assert stats["link_targets"] == ["Ventium"]
    assert stats["image_lines"] == 1
    assert stats["sections"] == 4


def test_source_matches_file_by_id_or_name():
    assert source_matches_file("Lore - Personen (idA)", META)
    assert source_matches_file("Lore - Personen (other)", META)
    assert not source_matches_file("Ander doc (idX)", META)


def test_compare_file_matches_pages_via_sources():
    result = compare_file(META, "Naam: Anna\nInformatie: lange tekst over Anna en {Ventium}.", PAGES)
    assert result["pages_from_file"] == ["Anna"]
    assert result["source"]["link_targets"] == ["Ventium"]
    assert result["links_on_site"] == ["Ventium"]
    assert result["coverage_ratio"] is not None


def test_compare_file_falls_back_to_title_in_text():
    meta = {"id": "idB", "name": "kaur", "mimeType": "application/vnd.google-apps.document"}
    pages = [{"title": "Baronie Kaurum", "content": "x", "infoboxRows": [], "sources": []}]
    result = compare_file(meta, "Baronie Kaurum (ook wel Het Land van Kaur) is een baronie.", pages)
    assert result["pages_from_file"] == ["Baronie Kaurum"]


def test_page_link_targets():
    assert page_link_targets(PAGES[0]) == ["Ventium"]


def test_build_report_detects_missing_links():
    per_file = [compare_file(META, "Tekst met {Bollet} en {Ventium}.", PAGES)]
    report = build_report(per_file, PAGES)
    assert report["link_targets_in_sources"] == ["Bollet", "Ventium"]
    assert report["link_targets_missing_on_site"] == ["Bollet"]
    assert report["pages_not_matched_to_any_file"] == ["Zonder bron"]
    assert report["totals"]["source_link_refs"] == 2
