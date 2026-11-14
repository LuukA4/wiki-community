import logging
import time

from . import chunking, drive_source, merge
from .config import SPREADSHEET_MIME
from .csv_parse import parse_timeline_csv
from .extract import Extractor
from .firestore_sink import FirestoreSink
from .page_builder import entity_to_page, timeline_events_to_page

log = logging.getLogger("lore_sync")


def source_ref(meta: dict) -> str:
    return f"{meta.get('name')} ({meta.get('id')})"


def is_skipped(title: str, sources_cfg: dict) -> bool:
    lowered = title.lower()
    return any(skip in lowered for skip in sources_cfg.get("skip_title_contains", []))


def resolve_types(title: str, mime: str, sources_cfg: dict) -> list:
    lowered = title.lower()
    for rule in sources_cfg.get("title_rules", []):
        if rule["match"] in lowered:
            return list(rule.get("types", []))
    if mime == SPREADSHEET_MIME:
        return list(sources_cfg.get("default_spreadsheet_types", ["timeline_event"]))
    return list(sources_cfg.get("default_types", []))


def collect_from_file(meta, text, types, sources_cfg, extractor, settings) -> dict:
    entities = {}
    mime = meta.get("mimeType", "")
    if mime == SPREADSHEET_MIME:
        if "timeline_event" in types:
            events = parse_timeline_csv(text)
            merge.merge_entities(entities, "timeline_event", events, source_ref(meta))
        ai_types = [t for t in types if t != "timeline_event"]
    else:
        ai_types = list(types)
    if ai_types:
        cleaned = chunking.clean_text(text)
        chunks = chunking.chunk_text(cleaned, settings.chunk_size, settings.chunk_overlap)
        log.info("  %d chunks extraheren uit %s", len(chunks), meta.get("name"))
        for chunk in chunks:
            parsed = extractor.extract_chunk(meta.get("name", ""), chunk, ai_types)
            for entity_type, items in parsed.items():
                merge.merge_entities(entities, entity_type, items, source_ref(meta))
    return entities


def build_pages(entities: dict, sources_cfg: dict) -> list:
    pages = []
    entity_pages = sources_cfg.get("entity_pages", {})
    for entity_type, bucket in entities.items():
        page_cfg = entity_pages.get(entity_type, {"category": entity_type, "caption": entity_type})
        if entity_type == "timeline_event":
            timeline_cfg = sources_cfg.get("timeline_page", {"title": "Tijdlijn", "category": "Tijdlijn"})
            pages.append(timeline_events_to_page(list(bucket.values()), timeline_cfg))
            continue
        for key, item in sorted(bucket.items()):
            item.setdefault("id", key)
            pages.append(entity_to_page(entity_type, item, page_cfg))
    return pages


def run_sync(settings, only_types=None) -> dict:
    sources_cfg = settings.sources
    service = drive_source.build_service(settings.google_credentials_json)
    extractor = Extractor(settings.mistral_api_key, settings.mistral_model, settings.request_pause)
    sink = FirestoreSink(
        settings.firebase_project_id,
        settings.firebase_credentials_json,
        settings.dry_run,
        pages_collection=sources_cfg.get("pages_collection", "pages"),
    )

    files = sorted(drive_source.iter_folder_files(service, settings.drive_folder_ids), key=lambda f: f.get("name", "").lower())
    log.info("%d bestanden gevonden in Drive", len(files))
    all_entities = {}
    file_summary = []
    for meta in files:
        if is_skipped(meta.get("name", ""), sources_cfg):
            log.info("Overslaan (regel): %s", meta.get("name"))
            continue
        if drive_source.EXPORT_MIME.get(meta.get("mimeType")) is None:
            log.info("Overslaan (type %s): %s", meta.get("mimeType"), meta.get("name"))
            continue
        if not settings.force:
            state = sink.get_state(meta["id"])
            if state and state.get("modifiedTime") == meta.get("modifiedTime"):
                log.info("Ongewijzigd, overslaan: %s", meta.get("name"))
                continue
        log.info("Verwerken: %s (%s)", meta.get("name"), meta.get("mimeType"))
        text = drive_source.export_file_text(service, meta)
        if not text.strip():
            log.info("  leeg, overslaan")
            continue
        types = resolve_types(meta.get("name", ""), meta.get("mimeType", ""), sources_cfg)
        if only_types:
            types = [t for t in types if t in only_types]
        if not types:
            log.info("  geen entiteitstypes voor deze titel, overslaan")
            continue
        entities = collect_from_file(meta, text, types, sources_cfg, extractor, settings)
        for entity_type, bucket in entities.items():
            merge.merge_entities(all_entities, entity_type, list(bucket.values()), source_ref(meta))
        file_summary.append({"file": meta.get("name"), "fileId": meta["id"], "entities": {t: len(b) for t, b in entities.items()}})
        sink.set_state(meta["id"], meta, {t: len(b) for t, b in entities.items()})
        time.sleep(settings.request_pause)

    pages = build_pages(all_entities, sources_cfg)
    written = skipped = 0
    for page in pages:
        result = sink.write_page(page, overwrite=settings.force)
        if result == "written":
            written += 1
        else:
            skipped += 1
            log.info("Pagina bestaat al, overgeslagen: %s", page["title"])
    log.info("Pagina's geschreven: %d, overgeslagen (bestaat al): %d", written, skipped)
    sink.write_run_summary(file_summary)
    return {
        "dry_run": settings.dry_run,
        "pages_written": written,
        "pages_skipped_existing": skipped,
        "pages_total": len(pages),
        "entities": {t: len(b) for t, b in all_entities.items()},
        "files": file_summary,
    }


def list_drive_files(settings) -> list:
    service = drive_source.build_service(settings.google_credentials_json)
    return [
        {"id": m["id"], "name": m.get("name"), "mimeType": m.get("mimeType"), "modifiedTime": m.get("modifiedTime")}
        for m in sorted(drive_source.iter_folder_files(service, settings.drive_folder_ids), key=lambda f: f.get("name", ""))
    ]
