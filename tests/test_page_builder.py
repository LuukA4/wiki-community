from lore_sync.page_builder import (
    build_content,
    build_title_index,
    doc_id_for_title,
    entity_to_page,
    resolve_page_links,
    resolve_wiki_links,
    sanitize_doc_id,
    timeline_events_to_page,
    to_wiki_links,
)

PAGE_CFG = {"category": "Personages", "caption": "Personage"}


def test_doc_id_matches_website_rule():
    assert doc_id_for_title("Krastus Suyckerbuyck I") == "Krastus_Suyckerbuyck_I"
    assert doc_id_for_title("  dubbele   spaties ") == "_dubbele_spaties_"


def test_doc_id_sanitizes_firestore_path_separator():
    assert doc_id_for_title("Opperraad / Hoge militaire raad") == "Opperraad_-_Hoge_militaire_raad"
    assert sanitize_doc_id("Familie Valderingen / Vintar-Valderingen".replace(" ", "_")) == "Familie_Valderingen_-_Vintar-Valderingen"
    assert "/" not in sanitize_doc_id("a/b/c")


def test_to_wiki_links_converts_drive_markers():
    assert to_wiki_links("{Krastus} en {Anna}") == "[[Krastus]] en [[Anna]]"
    assert to_wiki_links("geen links") == "geen links"
    assert to_wiki_links("") == ""


def test_entity_to_page_character():
    item = {
        "naam": "Krastus Suyckerbuyck I",
        "functie": "Koning",
        "titels": ["Koning van Castavonië"],
        "loyaliteit": ["Castavonië"],
        "geboortedatum": "-20",
        "geboorteplaats": "Ventium, Koringland",
        "leven": "Geboren in {Ventium}.",
        "informatie": "Koning van [[Castavonië]]-equivalent {Castavonië}.",
        "sources": ["doc A"],
    }
    page = entity_to_page("character", item, PAGE_CFG)
    assert page["docId"] == "Krastus_Suyckerbuyck_I"
    assert page["title"] == "Krastus Suyckerbuyck I"
    assert page["category"] == "Personages"
    assert page["infoboxCaption"] == "Personage"
    rows = {r["cells"][0]: r["cells"][1] for r in page["infoboxRows"] if len(r["cells"]) == 2}
    assert rows["Naam"] == "Krastus Suyckerbuyck I"
    assert rows["Functie"] == "Koning"
    assert rows["Titels"] == "Koning van Castavonië"
    assert rows["Loyaliteit"] == "Castavonië"
    assert rows["Geboorte"] == "-20, Ventium, Koringland"
    assert "## Leven" in page["content"]
    assert "[[Ventium]]" in page["content"]
    assert "[[Castavonië]]" in page["content"]


def test_entity_to_page_skips_empty_rows():
    page = entity_to_page("city", {"naam": "Ventium", "land": "Castavonië"}, {"category": "Steden", "caption": "Stad"})
    labels = [r["cells"][0] for r in page["infoboxRows"]]
    assert labels == ["Naam", "Land"]
    assert page["content"] == ""


def test_timeline_events_to_page_sorted():
    events = [
        {"jaar": 42, "titel": "Ontstaan koninkrijk", "detail": None, "groep": None},
        {"jaar": -1620, "titel": "Splitsing dwergenrijk", "detail": "Door {duister}", "groep": None},
        {"jaar": None, "titel": "Onbekend jaar", "detail": None, "groep": "X"},
    ]
    page = timeline_events_to_page(events, {"title": "Tijdlijn", "category": "Tijdlijn"})
    assert page["docId"] == "Tijdlijn"
    lines = page["content"].splitlines()
    assert lines[0].startswith("- **-1620**")
    assert "[[duister]]" in lines[0]
    assert lines[1].startswith("- **42**")
    assert lines[2].startswith("- **?**")
    assert "(X)" in lines[2]


def test_build_content_list_field():
    md = build_content("city", {"interessante_locaties": ["Balrût", "Haven"]})
    assert md == "## Interessante locaties\n\n- Balrût\n- Haven"


def test_to_wiki_links_drops_placeholder_markers():
    assert to_wiki_links("x {?} y {-} z {Anna}") == "x  y  z [[Anna]]"


def test_resolve_wiki_links_canonicalizes_to_existing_titles():
    index = build_title_index(["Ventium", "Castavonië"])
    assert resolve_wiki_links("[[ventium]] en [[Onbekend]]", index) == "[[Ventium]] en [[Onbekend]]"
    assert resolve_wiki_links("[[castavonie|het rijk]]", index) == "[[Castavonië|het rijk]]"


def test_resolve_page_links_fixes_content_and_infobox():
    index = build_title_index(["Ventium"])
    page = {
        "title": "Anna",
        "content": "Woont in [[ventium]].",
        "infoboxRows": [{"cells": ["Geboorteplaats", "[[VENTIUM]]"]}],
    }
    resolve_page_links(page, index)
    assert page["content"] == "Woont in [[Ventium]]."
    assert page["infoboxRows"][0]["cells"][1] == "[[Ventium]]"


def test_entity_to_page_adds_images_section():
    item = {
        "naam": "Kaurum",
        "beschrijving": "Baronie.",
        "afbeeldingen": ["![wapen](images/kaurum-wapen.png)"],
    }
    page = entity_to_page("region", item, {"category": "Regio's", "caption": "Regio"})
    assert "## Afbeeldingen\n\n![wapen](images/kaurum-wapen.png)" in page["content"]
    assert "## Beschrijving" in page["content"]
