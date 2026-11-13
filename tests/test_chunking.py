from lore_sync.chunking import chunk_text, clean_text, split_sections

SAMPLE = """Koninkrijk Voorbeeld\n\nNaam: Anna de Voorbeeldige\nFamilie: van Voorbeeld\nInformatie: Woont in de stad.\n\nNaam: {Bert} de Tweede\nFamilie: -\nInformatie: Broer van Anna.\n\nHoofdstuk 2\n\nNaam: Ciska\nInformatie: Stadsschilder.\n"""


def test_clean_text_strips_image_lines_and_blank_runs():
    text = "Stad X\n\nVentium.jpg\n\n\n\nBeschrijving van X\n"
    assert clean_text(text) == "Stad X\n\nBeschrijving van X"


def test_split_sections_breaks_on_naam_entries():
    sections = split_sections(SAMPLE)
    assert any(s.startswith("Naam: Anna") for s in sections)
    assert any(s.startswith("Naam: {Bert}") for s in sections)
    assert any(s.startswith("Naam: Ciska") for s in sections)


def test_chunk_text_respects_size_and_keeps_all_content():
    text = SAMPLE * 50
    chunks = chunk_text(text, chunk_size=400, overlap_sections=1)
    assert len(chunks) > 1
    assert all(len(c) <= 400 + 400 for c in chunks)
    joined = "".join(chunks)
    assert joined.count("Naam: Anna") >= 50


def test_chunk_text_oversized_section_is_hard_split():
    big = "x" * 5000
    chunks = chunk_text(big, chunk_size=1000, overlap_sections=0)
    assert len(chunks) == 5
    assert all(len(c) == 1000 for c in chunks)
