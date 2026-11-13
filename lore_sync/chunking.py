import re

ENTRY_START = re.compile(r"^\s*(?:#{1,6}\s+|\d+(?:\.\d+)*[.)]\s+|[A-ZÀ-Þ][\wÀ-ÿ'’\- ]{0,60}:)")
IMAGE_LINE = re.compile(r"^[\w\- .']+\.(?:jpg|jpeg|png|gif|webp|svg)$", re.IGNORECASE)


def clean_text(text: str) -> str:
    lines = [line for line in text.splitlines() if not IMAGE_LINE.match(line.strip())]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sections(text: str) -> list:
    sections = []
    current = []
    for line in text.splitlines(keepends=True):
        if current and ENTRY_START.match(line):
            sections.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("".join(current))
    return sections


def chunk_text(text: str, chunk_size: int = 60000, overlap_sections: int = 1) -> list:
    sections = split_sections(text)
    chunks = []
    start = 0
    buf = ""
    for i, section in enumerate(sections):
        if len(section) > chunk_size:
            if buf:
                chunks.append(buf)
                buf = ""
            for j in range(0, len(section), chunk_size):
                chunks.append(section[j : j + chunk_size])
            start = i + 1
            continue
        if buf and len(buf) + len(section) > chunk_size:
            chunks.append(buf)
            start = max(start, i - overlap_sections)
            buf = "".join(sections[start:i])
        buf += section
    if buf:
        chunks.append(buf)
    return chunks
