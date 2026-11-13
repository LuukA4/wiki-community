import logging
import time

from . import chunking, drive_source, merge
from .config import SPREADSHEET_MIME
from .csv_parse import parse_timeline_csv
from .extract import Extractor
from .firestore_sink import FirestoreSink

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


def run_sync(settings, only_types=None) -> list:
    sources_cfg = settings.sources
    service = drive_source.build_service(settings.google_credentials_json)
    extractor = Extractor(settings.mistral_api_key, settings.mistral_model, settings.request_pause)
    sink = FirestoreSink(settings.firebase_project_id, settings.firebase_credentials_json, settings.dry_run)

    files = sorted(drive_source.iter_folder_files(service, settings.drive_folder_ids), key=lambda f: f.get("name", "").lower())
    log.info("%d bestanden gevonden in Drive", len(files))
    summary = []
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
                log.info(" ongewijzigd, overslaan: %s", meta.get("name"))
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
        stats = {}
        collections = sources_cfg.get("entity_collections", {})
        for entity_type, bucket in entities.items():
            collection = collections.get(entity_type, entity_type)
            docs = []
            for key, item in bucket.items():
                item.setdefault("id", key)
                item["type"] = entity_type
                docs.append(item)
            count = sink.write_entities(collection, docs)
            stats[entity_type] = count
            log.info("  %s -> %s: %d documenten", entity_type, collection, count)
        sink.set_state(meta["id"], meta, stats)
        summary.append({"file": meta.get("name"), "fileId": meta["id"], "stats": stats})
        time.sleep(settings.request_pause)
    sink.write_run_summary(summary)
    return summary


def list_drive_files(settings) -> list:
    service = drive_source.build_service(settings.google_credentials_json)
    return [
        {"id": m["id"], "name": m.get("name"), "mimeType": m.get("mimeType"), "modifiedTime": m.get("modifiedTime")}
        for m in sorted(drive_source.iter_folder_files(service, settings.drive_folder_ids), key=lambda f: f.get("name", ""))
    ]
