import json

import pytest

from lore_sync.firestore_sink import FirestoreSink
from lore_sync.importer import import_images, import_pages, load_images_json, load_pages_json


def _write(tmp_path, data):
    path = tmp_path / "pages.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_pages_json_ok(tmp_path):
    path = _write(tmp_path, [{"docId": "Ventium", "title": "Ventium", "category": "Steden"}])
    pages = load_pages_json(path)
    assert pages[0]["docId"] == "Ventium"


def test_load_pages_json_rejects_missing_docid(tmp_path):
    path = _write(tmp_path, [{"title": "X"}])
    with pytest.raises(ValueError):
        load_pages_json(path)


def test_load_pages_json_rejects_non_array(tmp_path):
    path = _write(tmp_path, {"pages": []})
    with pytest.raises(ValueError):
        load_pages_json(path)


def test_load_pages_json_sanitizes_doc_id(tmp_path):
    path = _write(tmp_path, [{"docId": "Opperraad_/_Hoge_militaire_raad", "title": "Opperraad / Hoge militaire raad"}])
    pages = load_pages_json(path)
    assert pages[0]["docId"] == "Opperraad_-_Hoge_militaire_raad"


def test_import_pages_dry_run_counts(tmp_path):
    path = _write(tmp_path, [
        {"docId": "A", "title": "A"},
        {"docId": "B", "title": "B"},
    ])
    sink = FirestoreSink("", "", dry_run=True)
    result = import_pages(load_pages_json(path), sink)
    assert result == {"written": 2, "skipped_existing": 0, "total": 2}


class _StubSink(FirestoreSink):
    def __init__(self, existing):
        super().__init__("", "", dry_run=True)
        self.existing = existing

    def page_exists(self, doc_id):
        return doc_id in self.existing

    def write_page(self, page, overwrite=False):
        if not overwrite and self.page_exists(page["docId"]):
            return "skipped"
        return "written"


def test_import_pages_skips_existing_unless_force():
    pages = [{"docId": "A", "title": "A"}, {"docId": "B", "title": "B"}]
    assert import_pages(pages, _StubSink({"A"})) == {"written": 1, "skipped_existing": 1, "total": 2}
    assert import_pages(pages, _StubSink({"A"}), overwrite=True) == {"written": 2, "skipped_existing": 0, "total": 2}


def _write_images(tmp_path, data):
    path = tmp_path / "images.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_images_json_validates_and_sanitizes(tmp_path):
    path = _write_images(tmp_path, [
        {"name": "a/b.png", "data": "data:image/png;base64,AAA"},
        {"name": "ok.jpg", "data": "data:image/jpeg;base64,BBB"},
    ])
    images = load_images_json(path)
    assert images[0]["name"] == "a-b.png"
    with pytest.raises(ValueError):
        load_images_json(_write_images(tmp_path, [{"name": "x.png"}]))
    with pytest.raises(ValueError):
        load_images_json(_write_images(tmp_path, {"images": []}))


def test_import_images_dry_run_counts(tmp_path):
    path = _write_images(tmp_path, [
        {"name": "a.png", "data": "data:image/png;base64,AAA"},
        {"name": "b.jpg", "data": "data:image/jpeg;base64,BBB"},
    ])
    sink = FirestoreSink("", "", dry_run=True)
    assert import_images(load_images_json(path), sink) == {"written": 2, "skipped_existing": 0, "total": 2}


class _StubImageSink(FirestoreSink):
    def __init__(self, existing):
        super().__init__("", "", dry_run=True)
        self.existing = existing

    def image_exists(self, name):
        return name in self.existing

    def write_image(self, image, overwrite=False):
        if not overwrite and self.image_exists(image["name"]):
            return "skipped"
        return "written"


def test_import_images_skips_existing_unless_force():
    images = [{"name": "a.png", "data": "x"}, {"name": "b.jpg", "data": "y"}]
    assert import_images(images, _StubImageSink({"a.png"})) == {"written": 1, "skipped_existing": 1, "total": 2}
    assert import_images(images, _StubImageSink({"a.png"}), overwrite=True) == {"written": 2, "skipped_existing": 0, "total": 2}
