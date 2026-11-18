import json
import re

from . import drive_source
from .chunking import IMAGE_LINE, split_sections
from .merge import normalize_name

LINK_REF = re.compile(r"\{([^{}]+)\}")
WIKI_LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
PLACEHOLDERS = {"?", "-"}


def source_stats(text: str) -> dict:
    text = text or ""
    links = [m.group(1).strip() for m in LINK_REF.finditer(text)]
    links = [l for l in links if l not in PLACEHOLDERS]
    return {
        "chars": len(re.sub(r"\s+", " ", text)),
        "sections": len(split_sections(text)),
        "image_lines": sum(1 for line in text.splitlines() if IMAGE_LINE.match(line.strip())),
        "link_refs": len(links),
        "link_targets": sorted(set(links)),
    }


def page_text(page: dict) -> str:
    parts = [page.get("content") or ""]
    for row in page.get("infoboxRows", []):
        parts.extend(str(c) for c in row.get("cells", []))
    return " ".join(parts)


def page_link_targets(page: dict) -> list:
    return sorted({m.group(1).strip() for m in WIKI_LINK.finditer(page_text(page))})


def source_matches_file(source: str, meta: dict) -> bool:
    if meta.get("id") and meta["id"] in source:
        return True
    name = meta.get("name") or ""
    return bool(name) and name in source


def compare_file(meta: dict, text: str, pages: list) -> dict:
    stats = source_stats(text)
    norm_text = normalize_name(text)
    related = []
    for p in pages:
        if any(source_matches_file(s, meta) for s in p.get("sources", [])):
            related.append(p)
            continue
        title_norm = normalize_name(p.get("title") or "")
        if title_norm and title_norm in norm_text:
            related.append(p)
    page_chars = sum(len(page_text(p)) for p in related)
    content_chars = sum(len(p.get("content") or "") for p in related)
    page_links = sorted({t for p in related for t in page_link_targets(p)})
    return {
        "file": meta.get("name"),
        "fileId": meta.get("id"),
        "mimeType": meta.get("mimeType"),
        "source": stats,
        "pages_from_file": sorted(p.get("title") for p in related),
        "page_chars": page_chars,
        "content_chars": content_chars,
        "coverage_ratio": round(page_chars / stats["chars"], 3) if stats["chars"] else None,
        "content_coverage_ratio": round(content_chars / stats["chars"], 3) if stats["chars"] else None,
        "links_on_site": page_links,
    }


def build_report(per_file: list, pages: list) -> dict:
    source_links = sorted({t for f in per_file for t in f["source"]["link_targets"]})
    site_links = sorted({t for p in pages for t in page_link_targets(p)})
    site_norm = {normalize_name(t) for t in site_links}
    source_chars = sum(f["source"]["chars"] for f in per_file)
    page_chars = sum(f["page_chars"] for f in per_file)
    content_chars = sum(f.get("content_chars", 0) for f in per_file)
    matched_titles = {t for f in per_file for t in f["pages_from_file"]}
    return {
        "files": per_file,
        "totals": {
            "files": len(per_file),
            "source_chars": source_chars,
            "page_chars": page_chars,
            "content_chars": content_chars,
            "coverage_ratio": round(page_chars / source_chars, 3) if source_chars else None,
            "content_coverage_ratio": round(content_chars / source_chars, 3) if source_chars else None,
            "source_link_refs": sum(f["source"]["link_refs"] for f in per_file),
            "site_wiki_links": len(site_links),
            "source_image_lines": sum(f["source"]["image_lines"] for f in per_file),
        },
        "link_targets_in_sources": source_links,
        "link_targets_on_site": site_links,
        "link_targets_missing_on_site": [t for t in source_links if normalize_name(t) not in site_norm],
        "pages_not_matched_to_any_file": sorted(p.get("title") for p in pages if p.get("title") not in matched_titles),
    }


def run_verify(settings, pages: list) -> dict:
    sources_cfg = settings.sources
    service = drive_source.build_service(settings.google_credentials_json)
    files = sorted(
        drive_source.iter_folder_files(service, settings.drive_folder_ids),
        key=lambda f: f.get("name", "").lower(),
    )
    per_file = []
    for meta in files:
        if drive_source.EXPORT_MIME.get(meta.get("mimeType")) is None:
            continue
        name = meta.get("name", "")
        lowered = name.lower()
        if any(skip in lowered for skip in sources_cfg.get("skip_title_contains", [])):
            continue
        text = drive_source.export_file_text(service, meta)
        if not text.strip():
            continue
        per_file.append(compare_file(meta, text, pages))
    return build_report(per_file, pages)


def save_report(report: dict, path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
