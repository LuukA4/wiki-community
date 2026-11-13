from lore_sync.csv_parse import parse_timeline_csv

CSV = """Start Datum,Titel,Detail,Kleur,Groep
-1620,Splitsing van het rijk,Door het duister,nan,nan
nan,nan,nan,nan,nan
42,Ontstaan van de federatie,,blauw,Keizertijd
"""


def test_parse_timeline_csv_skips_empty_rows_and_nan():
    events = parse_timeline_csv(CSV)
    assert len(events) == 2
    assert events[0]["jaar"] == -1620
    assert events[0]["titel"] == "Splitsing van het rijk"
    assert events[0]["detail"] == "Door het duister"
    assert events[0]["groep"] is None
    assert events[1] == {"jaar": 42, "titel": "Ontstaan van de federatie", "detail": None, "groep": "Keizertijd", "kleur": "blauw"}


def test_parse_timeline_csv_bad_year_becomes_none():
    events = parse_timeline_csv("Start Datum,Titel\nabc,Event X\n")
    assert events[0]["jaar"] is None
