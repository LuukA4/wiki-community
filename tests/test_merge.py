from lore_sync.merge import entity_key, merge_entities, normalize_name, slugify


def test_slugify_and_normalize_strip_wiki_links():
    assert slugify("{Krastus} Suyckerbuyck I") == "krastus-suyckerbuyck-i"
    assert normalize_name("Dèlor!") == "delor"
    assert slugify("Groothertogdom Godrak") == "groothertogdom-godrak"


def test_merge_dedupes_same_character_across_sources():
    entities = {}
    merge_entities(
        entities,
        "character",
        [{"naam": "Anna de Voorbeeldige", "familie": "van Voorbeeld", "informatie": "Kort.", "loyaliteit": ["Voorbeeld"]}],
        "doc A (idA)",
    )
    merge_entities(
        entities,
        "character",
        [{"naam": "{Anna} de Voorbeeldige", "functie": "Koningin", "informatie": "Veel langere tekst over Anna.", "loyaliteit": ["Triumvantium"]}],
        "doc B (idB)",
    )
    assert len(entities["character"]) == 1
    merged = entities["character"]["anna-de-voorbeeldige"]
    assert merged["functie"] == "Koningin"
    assert merged["familie"] == "van Voorbeeld"
    assert merged["loyaliteit"] == ["Voorbeeld", "Triumvantium"]
    assert merged["informatie"] == "Veel langere tekst over Anna."
    assert merged["sources"] == ["doc A (idA)", "doc B (idB)"]


def test_merge_skips_items_without_name():
    entities = {}
    merge_entities(entities, "character", [{"familie": "X"}, {"naam": "Bert"}], "doc A")
    assert list(entities["character"].keys()) == ["bert"]


def test_timeline_key_includes_jaar():
    entities = {}
    merge_entities(
        entities,
        "timeline_event",
        [{"jaar": -500, "titel": "Val van rijk"}, {"jaar": 42, "titel": "Val van rijk"}],
        "sheet (idS)",
    )
    assert set(entities["timeline_event"].keys()) == {"val-van-rijk--500", "val-van-rijk-42"}
    assert entity_key("timeline_event", {"jaar": 7, "titel": "Slag"}) == "slag-7"
