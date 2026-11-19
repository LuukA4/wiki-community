import base64

from lore_sync.images import (
    MAX_DATA_URL_BYTES,
    block_images,
    convert_bare_image_lines,
    data_url_from_bytes,
    enforce_max_data_url,
    extract_embedded_images,
    image_name_from,
    image_refs_in_text,
)


def test_data_url_from_bytes_roundtrip():
    raw = b"\x89PNG\r\n\x1a\n"
    url = data_url_from_bytes(raw, "image/png")
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == raw


def test_image_name_from_uses_alt_or_prefix():
    assert image_name_from("Wapenschild Kaurum", "image/png", 1, "doc-") == "wapenschild-kaurum.png"
    assert image_name_from("", "image/jpeg", 3, "doc-") == "doc-image-3.jpg"
    assert image_name_from("", "image/png", 1) == "image-1.png"


def test_extract_embedded_images_replaces_data_uris():
    b64 = base64.b64encode(b"fakepng").decode()
    text = f"Tekst\n\n![wapen](data:image/png;base64,{b64})\n\nMeer tekst"
    cleaned, images = extract_embedded_images(text, prefix="personen-")
    assert len(images) == 1
    assert images[0]["name"] == "wapen.png"
    assert images[0]["data"] == f"data:image/png;base64,{b64}"
    assert "![wapen](images/wapen.png)" in cleaned
    assert "data:image" not in cleaned


def test_extract_embedded_images_drops_oversized():
    big = base64.b64encode(b"x" * (MAX_DATA_URL_BYTES + 10)).decode()
    text = f"![groot](data:image/png;base64,{big})"
    cleaned, images = extract_embedded_images(text, max_bytes=1000)
    assert images == []
    assert "data:image" not in cleaned


def test_enforce_max_data_url_keeps_small_and_rejects_big_without_pillow():
    small = {"name": "a.png", "data": data_url_from_bytes(b"123", "image/png")}
    assert enforce_max_data_url(small, 700_000) is small
    big = {"name": "b.png", "data": data_url_from_bytes(b"x" * 100_000, "image/png")}
    assert enforce_max_data_url(big, 1000) is None or enforce_max_data_url(big, 1000)["data"] != big["data"]


def test_convert_bare_image_lines():
    text = "Stad X\n\nDèlor2.jpg\n\nBeschrijving"
    converted, names = convert_bare_image_lines(text)
    assert names == ["Dèlor2.jpg"]
    assert "![Dèlor2.jpg](images/Dèlor2.jpg)" in converted
    assert "Beschrijving" in converted


def test_block_images_maps_naam_blocks():
    text = (
        "Naam: Anna\nInformatie: woont in Ventium.\n![portret](images/anna.png)\n\n"
        "Naam: Bert\nInformatie: broer van Anna.\n"
    )
    mapping = block_images(text)
    assert mapping == {"anna": ["![portret](images/anna.png)"]}


def test_image_refs_in_text():
    assert image_refs_in_text("x ![a](images/a.png) y") == ["![a](images/a.png)"]
