import re

from .merge import normalize_name
from .schemas import name_field

WIKILINK = re.compile(r"\{([^{}]+)\}")
WIKI_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")
LINK_PLACEHOLDERS = {"?", "-"}


def to_wiki_links(text) -> str:
    if not text:
        return ""

    def repl(m):
        inner = m.group(1).strip()
        if inner in LINK_PLACEHOLDERS:
            return ""
        return f"[[{inner}]]"

    return WIKILINK.sub(repl, str(text))


def build_title_index(titles) -> dict:
    return {normalize_name(t): t for t in titles if t}


def resolve_wiki_links(text, title_index: dict):
    if not text:
        return text or ""

    def repl(m):
        target, label = m.group(1).strip(), m.group(2)
        canonical = title_index.get(normalize_name(target))
        if not canonical:
            return m.group(0)
        return f"[[{canonical}|{label}]]" if label else f"[[{canonical}]]"

    return WIKI_LINK.sub(repl, str(text))


def resolve_page_links(page: dict, title_index: dict) -> dict:
    page["content"] = resolve_wiki_links(page.get("content", ""), title_index)
    for row in page.get("infoboxRows", []):
        row["cells"] = [resolve_wiki_links(c, title_index) if isinstance(c, str) else c for c in row.get("cells", [])]
    return page


def sanitize_doc_id(doc_id: str) -> str:
    return str(doc_id).replace("/", "-")


def doc_id_for_title(title: str) -> str:
    return sanitize_doc_id(re.sub(r"\s+", "_", title))


def _cell_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return to_wiki_links(", ".join(str(v) for v in value))
    return to_wiki_links(str(value))


INFOBOX_ROWS = {
    "character": [
        ("Naam", "naam"),
        ("Bijnaam", "bijnaam"),
        ("Familie", "familie"),
        ("Functie", "functie"),
        ("Titels", "titels"),
        ("Eigendommen", "eigendommen"),
        ("Loyaliteit", "loyaliteit"),
        ("Religie", "religie"),
        ("Geboorte", ("geboortedatum", "geboorteplaats")),
        ("Sterfte", ("sterfdatum", "sterfteplaats")),
        ("Echtgenoot", "echtgenoot"),
        ("Kinderen", "kinderen"),
        ("Vader", "vader"),
        ("Moeder", "moeder"),
        ("Broers/zussen", "broers_zussen"),
        ("Wapenschild", "wapenschild"),
        ("Familiewapen", "familiewapen"),
        ("Embleem", "embleem"),
        ("Uiterlijk", "uiterlijk"),
        ("Persoonlijkheid", "persoonlijkheid"),
    ],
    "country": [
        ("Naam", "naam"),
        ("Type", "type"),
        ("Motto", "motto"),
        ("Hoofdstad", "hoofdstad"),
        ("Heerser", "heerser"),
        ("Regeringsvorm", "regeringsvorm"),
        ("Staatsreligies", "religies"),
        ("Beschrijving", "beschrijving"),
    ],
    "region": [
        ("Naam", "naam"),
        ("Type", "type"),
        ("Land", "land"),
        ("Hoofdstad", "hoofdstad"),
        ("Heerser", "heerser"),
        ("Beschrijving", "beschrijving"),
    ],
    "city": [
        ("Naam", "naam"),
        ("Land", "land"),
        ("Regio", "regio"),
        ("Beschrijving", "beschrijving"),
    ],
    "organization": [
        ("Naam", "naam"),
        ("Type", "type"),
        ("Leider", "leider"),
        ("Locatie", "locatie"),
        ("Leden", "leden"),
        ("Beschrijving", "beschrijving"),
    ],
    "deity": [
        ("Naam", "naam"),
        ("Titel", "titel"),
        ("Domeinen", "domeinen"),
        ("Beschrijving", "beschrijving"),
    ],
    "religion": [
        ("Naam", "naam"),
        ("Goden", "goden"),
        ("Beschrijving", "beschrijving"),
    ],
    "item": [
        ("Naam", "naam"),
        ("Type", "type"),
        ("Eigenaar", "eigenaar"),
        ("Beschrijving", "beschrijving"),
    ],
}

CONTENT_SECTIONS = {
    "character": [("Leven", "leven"), ("Overige informatie", "informatie")],
    "city": [("Beschrijving", "beschrijving"), ("Interessante locaties", "interessante_locaties")],
}
DEFAULT_CONTENT_SECTIONS = [("Beschrijving", "beschrijving")]


def _section_markdown(label: str, value) -> str:
    if value is None or value == "" or value == []:
        return ""
    if isinstance(value, list):
        items = [to_wiki_links(str(v)) for v in value if v]
        if not items:
            return ""
        body = "\n".join(f"- {item}" for item in items)
    else:
        body = to_wiki_links(str(value))
    return f"## {label}\n\n{body}"


def build_content(entity_type: str, item: dict) -> str:
    sections = []
    for label, field in CONTENT_SECTIONS.get(entity_type, DEFAULT_CONTENT_SECTIONS):
        md = _section_markdown(label, item.get(field))
        if md:
            sections.append(md)
    return "\n\n".join(sections)


def entity_to_page(entity_type: str, item: dict, page_cfg: dict) -> dict:
    title = str(item.get(name_field(entity_type), "")).strip()
    rows = []
    for label, spec in INFOBOX_ROWS.get(entity_type, [("Naam", "naam"), ("Beschrijving", "beschrijving")]):
        if isinstance(spec, tuple):
            value = ", ".join(str(item.get(f)) for f in spec if item.get(f))
            value = to_wiki_links(value) if value else ""
        else:
            value = _cell_value(item.get(spec))
        if value:
            rows.append({"cells": [label, value]})
    content = build_content(entity_type, item)
    image_lines = [str(x) for x in item.get("afbeeldingen", []) if x]
    if image_lines:
        section = "## Afbeeldingen\n\n" + "\n".join(image_lines)
        content = f"{content}\n\n{section}" if content else section
    return {
        "docId": doc_id_for_title(title),
        "title": title,
        "category": page_cfg.get("category", entity_type),
        "infoboxCaption": page_cfg.get("caption", page_cfg.get("category", entity_type)),
        "infoboxRows": rows,
        "content": content,
        "sourceEntityType": entity_type,
        "sources": item.get("sources", []),
    }


def timeline_events_to_page(events: list, page_cfg: dict) -> dict:
    def sort_key(event):
        jaar = event.get("jaar")
        return (jaar is None, jaar if jaar is not None else 0, event.get("titel", ""))

    lines = []
    for event in sorted(events, key=sort_key):
        jaar = event.get("jaar")
        titel = to_wiki_links(event.get("titel", ""))
        detail = to_wiki_links(event.get("detail") or "")
        groep = to_wiki_links(event.get("groep") or "")
        line = f"- **{jaar if jaar is not None else '?'}** — {titel}"
        if detail:
            line += f": {detail}"
        if groep:
            line += f" ({groep})"
        lines.append(line)
    title = page_cfg.get("title", "Tijdlijn")
    return {
        "docId": doc_id_for_title(title),
        "title": title,
        "category": page_cfg.get("category", "Tijdlijn"),
        "infoboxCaption": page_cfg.get("caption", "Tijdlijn"),
        "infoboxRows": [],
        "content": "\n".join(lines),
        "sourceEntityType": "timeline_event",
    }
