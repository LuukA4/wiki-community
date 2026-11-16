import json

from lore_sync.extract import build_user_prompt, parse_json_object
from lore_sync.schemas import ITEM_SCHEMAS, build_extract_schema, schema_json


def test_parse_json_object_plain_and_fenced():
    assert parse_json_object('{"a": 1}') == {"a": 1}
    assert parse_json_object('```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}
    assert parse_json_object("tekst ervoor {\"b\": true} tekst erna") == {"b": True}
    assert parse_json_object("geen json hier") == {}
    assert parse_json_object("") == {}


def test_build_extract_schema_contains_requested_types_only():
    schema = build_extract_schema(["character", "timeline_event"])
    assert set(schema["properties"].keys()) == {"character", "timeline_event"}
    assert schema["properties"]["character"]["items"] == ITEM_SCHEMAS["character"]
    json.dumps(schema)


def test_build_extract_schema_rejects_unknown_type():
    try:
        build_extract_schema(["draak"])
    except ValueError:
        return
    raise AssertionError("ValueError verwacht voor onbekend type")


def test_schema_json_is_valid_json():
    parsed = json.loads(schema_json(["city"]))
    assert "city" in parsed["properties"]


def test_build_user_prompt_contains_title_schema_and_text():
    prompt = build_user_prompt("Lore - Personen", "Naam: X\n", ["character"])
    assert "Lore - Personen" in prompt
    assert "Naam: X" in prompt
    assert '"character"' in prompt
