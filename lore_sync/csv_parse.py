import csv
import io


def _clean(value):
    if value is None:
        return None
    value = value.strip()
    if value == "" or value.lower() == "nan":
        return None
    return value


def parse_timeline_csv(text: str) -> list:
    reader = csv.DictReader(io.StringIO(text))
    events = []
    for row in reader:
        titel = _clean(row.get("Titel"))
        if not titel:
            continue
        jaar_raw = _clean(row.get("Start Datum"))
        jaar = None
        if jaar_raw:
            try:
                jaar = int(float(jaar_raw.replace(",", ".")))
            except ValueError:
                jaar = None
        events.append(
            {
                "jaar": jaar,
                "titel": titel,
                "detail": _clean(row.get("Detail")),
                "groep": _clean(row.get("Groep")),
                "kleur": _clean(row.get("Kleur")),
            }
        )
    return events
