import json

from .firestore_sink import FirestoreSink
from .page_builder import sanitize_doc_id


def load_pages_json(path) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path} moet een JSON-array van pagina's bevatten")
    pages = []
    for i, page in enumerate(data):
        if not isinstance(page, dict) or not page.get("docId") or not page.get("title"):
            raise ValueError(f"pagina #{i} in {path} mist 'docId' of 'title'")
        page["docId"] = sanitize_doc_id(page["docId"])
        pages.append(page)
    return pages


def import_pages(pages: list, sink: FirestoreSink, overwrite: bool = False) -> dict:
    written = skipped = 0
    for page in pages:
        if sink.write_page(page, overwrite=overwrite) == "written":
            written += 1
        else:
            skipped += 1
    return {"written": written, "skipped_existing": skipped, "total": len(pages)}


def load_images_json(path) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path} moet een JSON-array van afbeeldingen bevatten")
    images = []
    for i, image in enumerate(data):
        if not isinstance(image, dict) or not image.get("name") or not image.get("data"):
            raise ValueError(f"afbeelding #{i} in {path} mist 'name' of 'data'")
        image["name"] = sanitize_doc_id(str(image["name"]))
        images.append(image)
    return images


def import_images(images: list, sink: FirestoreSink, overwrite: bool = False) -> dict:
    written = skipped = 0
    for image in images:
        if sink.write_image(image, overwrite=overwrite) == "written":
            written += 1
        else:
            skipped += 1
    return {"written": written, "skipped_existing": skipped, "total": len(images)}
