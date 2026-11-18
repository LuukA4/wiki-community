import base64
import io
import re

from .chunking import IMAGE_LINE
from .merge import normalize_name, slugify

MAX_DATA_URL_BYTES = 700_000

DATA_URI_IMAGE = re.compile(r"!\[([^\]]*)\]\(data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)\)")
IMAGE_REF = re.compile(r"!\[[^\]]*\]\(images/[^)]+\)")
NAME_LINE = re.compile(r"^\s*Naam:\s*(.+?)\s*$", re.MULTILINE)
DATA_URL = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.*)$", re.DOTALL)

MIME_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
}


def data_url_from_bytes(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def image_name_from(alt: str, mime: str, n: int, prefix: str = "") -> str:
    ext = MIME_EXT.get((mime or "").lower(), ".img")
    base = slugify(alt)[:60] if alt else ""
    if not base:
        base = f"{prefix}image-{n}" if prefix else f"image-{n}"
    return base if base.endswith(ext) else base + ext


def _downscale(data_url: str, max_bytes: int):
    try:
        from PIL import Image
    except ImportError:
        return None
    m = DATA_URL.match(data_url)
    if not m:
        return None
    mime, b64 = m.group(1), m.group(2)
    try:
        raw = base64.b64decode(b64)
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
        quality = 85
        while True:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            candidate = data_url_from_bytes(buf.getvalue(), "image/jpeg")
            if len(candidate.encode()) <= max_bytes or min(img.size) <= 320:
                return candidate if len(candidate.encode()) <= max_bytes else None
            if img.size[0] <= 640 and img.size[1] <= 640:
                return None
            img = img.resize((max(320, img.size[0] // 2), max(320, img.size[1] // 2)))
            quality = max(40, quality - 15)
    except Exception:
        return None


def enforce_max_data_url(image: dict, max_bytes: int = MAX_DATA_URL_BYTES):
    data = image.get("data") or ""
    if len(data.encode()) <= max_bytes:
        return image
    smaller = _downscale(data, max_bytes)
    if smaller is None:
        return None
    image = dict(image)
    image["data"] = smaller
    return image


def extract_embedded_images(text: str, prefix: str = "", max_bytes: int = MAX_DATA_URL_BYTES):
    images = []

    def repl(m):
        alt, mime, b64 = m.group(1), m.group(2), re.sub(r"\s", "", m.group(3))
        data_url = f"data:{mime};base64,{b64}"
        image = {"name": "", "data": data_url, "alt": alt}
        image = enforce_max_data_url(image, max_bytes)
        if image is None:
            return alt
        n = len(images) + 1
        image["name"] = image_name_from(alt, mime, n, prefix)
        images.append(image)
        return f"![{alt or image['name']}](images/{image['name']})"

    return DATA_URI_IMAGE.sub(repl, text), images


def convert_bare_image_lines(text: str):
    out = []
    names = []
    for line in text.splitlines():
        stripped = line.strip()
        if IMAGE_LINE.match(stripped):
            names.append(stripped)
            out.append(f"![{stripped}](images/{stripped})")
        else:
            out.append(line)
    return "\n".join(out), names


def block_images(text: str) -> dict:
    result = {}
    matches = list(NAME_LINE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        key = normalize_name(m.group(1))
        refs = IMAGE_REF.findall(text[m.start() : end])
        if refs:
            result.setdefault(key, []).extend(refs)
    return result


def image_refs_in_text(text: str) -> list:
    return IMAGE_REF.findall(text or "")
