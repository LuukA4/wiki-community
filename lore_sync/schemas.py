import json

CHARACTER = {
    "type": "object",
    "properties": {
        "naam": {"type": "string"},
        "bijnaam": {"type": ["string", "null"]},
        "familie": {"type": ["string", "null"]},
        "functie": {"type": ["string", "null"]},
        "titels": {"type": "array", "items": {"type": "string"}},
        "eigendommen": {"type": ["string", "null"]},
        "loyaliteit": {"type": "array", "items": {"type": "string"}},
        "religie": {"type": "array", "items": {"type": "string"}},
        "geboortedatum": {"type": ["string", "null"]},
        "geboorteplaats": {"type": ["string", "null"]},
        "sterfdatum": {"type": ["string", "null"]},
        "sterfteplaats": {"type": ["string", "null"]},
        "echtgenoot": {"type": ["string", "null"]},
        "kinderen": {"type": "array", "items": {"type": "string"}},
        "vader": {"type": ["string", "null"]},
        "moeder": {"type": ["string", "null"]},
        "broers_zussen": {"type": "array", "items": {"type": "string"}},
        "wapenschild": {"type": ["string", "null"]},
        "familiewapen": {"type": ["string", "null"]},
        "embleem": {"type": ["string", "null"]},
        "uiterlijk": {"type": ["string", "null"]},
        "persoonlijkheid": {"type": ["string", "null"]},
        "leven": {"type": ["string", "null"]},
        "informatie": {"type": ["string", "null"]},
    },
    "required": ["naam"],
}

COUNTRY = {
    "type": "object",
    "properties": {
        "naam": {"type": "string"},
        "type": {"type": ["string", "null"]},
        "motto": {"type": ["string", "null"]},
        "hoofdstad": {"type": ["string", "null"]},
        "regeringsvorm": {"type": ["string", "null"]},
        "heerser": {"type": ["string", "null"]},
        "religies": {"type": "array", "items": {"type": "string"}},
        "beschrijving": {"type": ["string", "null"]},
    },
    "required": ["naam"],
}

REGION = {
    "type": "object",
    "properties": {
        "naam": {"type": "string"},
        "type": {"type": ["string", "null"]},
        "land": {"type": ["string", "null"]},
        "hoofdstad": {"type": ["string", "null"]},
        "heerser": {"type": ["string", "null"]},
        "beschrijving": {"type": ["string", "null"]},
    },
    "required": ["naam"],
}

CITY = {
    "type": "object",
    "properties": {
        "naam": {"type": "string"},
        "land": {"type": ["string", "null"]},
        "regio": {"type": ["string", "null"]},
        "beschrijving": {"type": ["string", "null"]},
        "interessante_locaties": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["naam"],
}

TIMELINE_EVENT = {
    "type": "object",
    "properties": {
        "jaar": {"type": ["integer", "null"]},
        "titel": {"type": "string"},
        "detail": {"type": ["string", "null"]},
        "groep": {"type": ["string", "null"]},
        "kleur": {"type": ["string", "null"]},
    },
    "required": ["titel"],
}

ORGANIZATION = {
    "type": "object",
    "properties": {
        "naam": {"type": "string"},
        "type": {"type": ["string", "null"]},
        "leider": {"type": ["string", "null"]},
        "locatie": {"type": ["string", "null"]},
        "leden": {"type": "array", "items": {"type": "string"}},
        "beschrijving": {"type": ["string", "null"]},
    },
    "required": ["naam"],
}

DEITY = {
    "type": "object",
    "properties": {
        "naam": {"type": "string"},
        "titel": {"type": ["string", "null"]},
        "domeinen": {"type": "array", "items": {"type": "string"}},
        "beschrijving": {"type": ["string", "null"]},
    },
    "required": ["naam"],
}

RELIGION = {
    "type": "object",
    "properties": {
        "naam": {"type": "string"},
        "goden": {"type": "array", "items": {"type": "string"}},
        "beschrijving": {"type": ["string", "null"]},
    },
    "required": ["naam"],
}

ITEM = {
    "type": "object",
    "properties": {
        "naam": {"type": "string"},
        "type": {"type": ["string", "null"]},
        "eigenaar": {"type": ["string", "null"]},
        "beschrijving": {"type": ["string", "null"]},
    },
    "required": ["naam"],
}

ITEM_SCHEMAS = {
    "character": CHARACTER,
    "country": COUNTRY,
    "region": REGION,
    "city": CITY,
    "timeline_event": TIMELINE_EVENT,
    "organization": ORGANIZATION,
    "deity": DEITY,
    "religion": RELIGION,
    "item": ITEM,
}

NAME_FIELD = {
    "timeline_event": "titel",
}


def name_field(entity_type: str) -> str:
    return NAME_FIELD.get(entity_type, "naam")


def build_extract_schema(types) -> dict:
    unknown = [t for t in types if t not in ITEM_SCHEMAS]
    if unknown:
        raise ValueError(f"Onbekende entiteitstypes: {unknown}")
    return {
        "type": "object",
        "properties": {t: {"type": "array", "items": ITEM_SCHEMAS[t]} for t in types},
        "additionalProperties": False,
    }


def schema_json(types) -> str:
    return json.dumps(build_extract_schema(types), ensure_ascii=False, indent=2)
