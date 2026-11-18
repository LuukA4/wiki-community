import re
import unicodedata

from .schemas import name_field

TEXT_FIELDS = {
    "informatie",
    "leven",
    "beschrijving",
    "detail",
    "uiterlijk",
    "persoonlijkheid",
    "motto",
    "titels_tekst",
}


def strip_link_markers(value):
    return re.sub(r"[{}\[\]]", "", value) if isinstance(value, str) else value


def normalize_name(name: str) -> str:
    name = strip_link_markers(name or "")
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[^\w\s-]", " ", name, flags=re.UNICODE).lower()
    return re.sub(r"\s+", " ", name).strip()


def slugify(name: str) -> str:
    name = unicodedata.normalize("NFKD", strip_link_markers(name or ""))
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return name or "onbekend"


def entity_key(entity_type: str, item: dict) -> str:
    name = item.get(name_field(entity_type), "")
    slug = slugify(name)
    if entity_type == "timeline_event" and item.get("jaar") is not None:
        slug = f"{slug}-{item['jaar']}"
    return slug


def _is_empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def merge_item(existing: dict, new: dict) -> dict:
    for key, value in new.items():
        if _is_empty(value):
            continue
        if key not in existing or _is_empty(existing[key]):
            existing[key] = value
        elif isinstance(existing[key], list) and isinstance(value, list):
            merged = list(existing[key])
            for v in value:
                if v not in merged:
                    merged.append(v)
            existing[key] = merged
        elif isinstance(existing[key], dict) and isinstance(value, dict):
            existing[key] = merge_item(existing[key], value)
        elif key in TEXT_FIELDS and isinstance(value, str) and len(value) > len(str(existing[key])):
            existing[key] = value
    return existing


def merge_entities(entities_by_type: dict, entity_type: str, items, source: str) -> dict:
    bucket = entities_by_type.setdefault(entity_type, {})
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        name_key = name_field(entity_type)
        if isinstance(item.get(name_key), str):
            item[name_key] = strip_link_markers(item[name_key]).strip()
        if not item.get(name_key):
            continue
        key = entity_key(entity_type, item)
        if key in bucket:
            bucket[key] = merge_item(bucket[key], item)
            sources = bucket[key].setdefault("sources", [])
            if source not in sources:
                sources.append(source)
        else:
            item["sources"] = [source]
            bucket[key] = item
    return bucket
