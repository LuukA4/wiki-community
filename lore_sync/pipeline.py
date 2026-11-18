import json
import logging
import time
from pathlib import Path

from . import chunking, drive_source, images, merge
from .config import SPREADSHEET_MIME
from .csv_parse import parse_timeline_csv
from .extract import Extractor
from .firestore_sink import FirestoreSink
from .merge import normalize_name
from .page_builder import build_title_index, entity_to_page, resolve_page_links, timeline_events_to_page
from .schemas import name_field

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
    title_index = build_title_index([p["title"] for p in pages])
    for page in pages:
        resolve_page_links(page, title_index)
    return pages


def collect_drive_image(service, meta: dict, mime: str, all_images: dict, max_image_bytes: int, export_mime: str = None) -> str:
    if export_mime:
        raw = drive_source.export_file_bytes(service, meta["id"], export_mime)
    else:
        raw = drive_source.download_file_bytes(service, meta["id"])
    image = {
        "name": meta.get("name", ""),
        "data": images.data_url_from_bytes(raw, mime),
        "source": source_ref(meta),
    }
    image = images.enforce_max_data_url(image, max_image_bytes)
    if image is None:
        log.warning("Afbeelding te groot (>%d bytes als data-URL), overgeslagen: %s", max_image_bytes, meta.get("name"))
        return "skipped_too_big"
    all_images[image["name"]] = image
    return "collected"


def run_sync(settings, only_types=None, output_path=None) -> dict:
    sources_cfg = settings.sources
    service = drive_source.build_service(settings.google_credentials_json)
    extractor = Extractor(settings.mistral_api_key, settings.mistral_model, settings.request_pause)
    max_image_bytes = int(sources_cfg.get("max_image_data_url_bytes", images.MAX_DATA_URL_BYTES))
    sink = FirestoreSink(
        settings.firebase_project_id,
        settings.firebase_credentials_json,
        settings.dry_run,
        pages_collection=sources_cfg.get("pages_collection", "pages"),
        images_collection=sources_cfg.get("images_collection", "images"),
    )

    files = sorted(drive_source.iter_folder_files(service, settings.drive_folder_ids), key=lambda f: f.get("name", "").lower())
    log.info("%d bestanden gevonden in Drive", len(files))
    all_entities = {}
    all_images = {}
    file_summary = []
    image_summary = []
    for meta in files:
        mime = meta.get("mimeType", "")
        if is_skipped(meta.get("name", ""), sources_cfg):
            log.info("Overslaan (regel): %s", meta.get("name"))
            continue
        if drive_source.is_image_mime(mime):
            status = collect_drive_image(service, meta, mime, all_images, max_image_bytes)
            image_summary.append({"file": meta.get("name"), "fileId": meta["id"], "status": status})
            continue
        if mime == drive_source.DRAWING_MIME:
            drawing_meta = dict(meta, name=f"{meta.get('name', '')}.png")
            status = collect_drive_image(
                service, drawing_meta, drive_source.DRAWING_EXPORT_MIME, all_images, max_image_bytes,
                export_mime=drive_source.DRAWING_EXPORT_MIME,
            )
            image_summary.append({"file": meta.get("name"), "fileId": meta["id"], "status": status})
            continue
        if drive_source.EXPORT_MIME.get(mime) is None:
            log.info("Overslaan (type %s): %s", mime, meta.get("name"))
            continue
        if not settings.force:
            state = sink.get_state(meta["id"])
            if state and state.get("modifiedTime") == meta.get("modifiedTime"):
                log.info("Ongewijzigd, overslaan: %s", meta.get("name"))
                continue
        log.info("Verwerken: %s (%s)", meta.get("name"), mime)
        text = drive_source.export_file_text(service, meta)
        if not text.strip():
            log.info("  leeg, overslaan")
            continue
        text, embedded = images.extract_embedded_images(
            text, prefix=f"{merge.slugify(meta.get('name', 'doc'))}-", max_bytes=max_image_bytes
        )
        for image in embedded:
            all_images[image["name"]] = image
        text, _bare = images.convert_bare_image_lines(text)
        block_map = images.block_images(text)
        types = resolve_types(meta.get("name", ""), mime, sources_cfg)
        if only_types:
            types = [t for t in types if t in only_types]
        if not types:
            log.info("  geen entiteitstypes voor deze titel, overslaan")
            continue
        entities = collect_from_file(meta, text, types, sources_cfg, extractor, settings)
        for entity_type, bucket in entities.items():
            nf = name_field(entity_type)
            for item in bucket.values():
                key = normalize_name(str(item.get(nf, "")))
                if key in block_map:
                    item.setdefault("afbeeldingen", []).extend(block_map[key])
            merge.merge_entities(all_entities, entity_type, list(bucket.values()), source_ref(meta))
        file_summary.append({"file": meta.get("name"), "fileId": meta["id"], "entities": {t: len(b) for t, b in entities.items()}})
        sink.set_state(meta["id"], meta, {t: len(b) for t, b in entities.items()})
        time.sleep(settings.request_pause)

    pages = build_pages(all_entities, sources_cfg)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(pages, fh, ensure_ascii=False, indent=2)
        log.info("Pagina's weggeschreven naar %s", output_path)
        images_path = Path(output_path).parent / "images.json"
        with open(images_path, "w", encoding="utf-8") as fh:
            json.dump(list(all_images.values()), fh, ensure_ascii=False, indent=2)
        log.info("Afbeeldingen weggeschreven naar %s", images_path)
    written = skipped = 0
    for page in pages:
        result = sink.write_page(page, overwrite=settings.force)
        if result == "written":
            written += 1
        else:
            skipped += 1
            log.info("Pagina bestaat al, overgeslagen: %s", page["title"])
    log.info("Pagina's geschreven: %d, overgeslagen (bestaat al): %d", written, skipped)
    img_written = img_skipped = 0
    for image in all_images.values():
        if sink.write_image(image, overwrite=settings.force) == "written":
            img_written += 1
        else:
            img_skipped += 1
    log.info("Afbeeldingen geschreven: %d, overgeslagen (bestaat al): %d", img_written, img_skipped)
    sink.write_run_summary(file_summary)
    return {
        "dry_run": settings.dry_run,
        "pages_written": written,
        "pages_skipped_existing": skipped,
        "pages_total": len(pages),
        "images_written": img_written,
        "images_skipped_existing": img_skipped,
        "images_total": len(all_images),
        "entities": {t: len(b) for t, b in all_entities.items()},
        "files": file_summary,
        "images": image_summary,
    }


def list_drive_files(settings) -> list:
    service = drive_source.build_service(settings.google_credentials_json)
    return [
        {"id": m["id"], "name": m.get("name"), "mimeType": m.get("mimeType"), "modifiedTime": m.get("modifiedTime")}
        for m in sorted(drive_source.iter_folder_files(service, settings.drive_folder_ids), key=lambda f: f.get("name", ""))
    ]
