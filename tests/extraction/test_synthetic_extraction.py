"""The deterministic extractors, run on the ingested synthetic mails, agree with the gold."""

import json
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from eshipping_ai.adapters.mail_files import FolderMailSource, MailFileParser
from eshipping_ai.adapters.object_store import LocalObjectStore
from eshipping_ai.adapters.pdf_text import PdfTextParser
from eshipping_ai.application.ingest import IngestMail
from eshipping_ai.extraction.dates import find_dates
from eshipping_ai.extraction.equipment import find_equipment
from eshipping_ai.extraction.locations import find_locations
from eshipping_ai.extraction.references import ReferenceKind, find_references

MADRID = ZoneInfo("Europe/Madrid")


def ingested_texts(synthetic_dir: Path, tmp_path: Path, inbox, clock):  # type: ignore[no-untyped-def]
    IngestMail(
        FolderMailSource(synthetic_dir / "mails", "operaciones"),
        MailFileParser(),
        PdfTextParser(),
        inbox,
        LocalObjectStore(tmp_path),
        clock,
        MADRID,
    ).run()
    store = LocalObjectStore(tmp_path)
    return [(m, store.get(m.clean_body_key).decode()) for m in inbox.messages.values()]


def test_containers_and_bookings_in_the_gold_are_found(synthetic_dir, tmp_path, inbox, clock):  # type: ignore[no-untyped-def]
    gold = json.loads((synthetic_dir / "gold.json").read_text(encoding="utf-8"))
    texts = ingested_texts(synthetic_dir, tmp_path, inbox, clock)
    found = {(m.kind, m.value) for _, text in texts for m in find_references(text) if m.valid}
    for fields in gold["expedientes"].values():
        for number in fields["equipment"]["value"]["containers"]:
            assert (ReferenceKind.CONTAINER, number) in found
        assert (ReferenceKind.BOOKING, fields["booking"]["value"]) in found


def test_the_rollover_notice_gives_vessel_dates_alias_and_equipment(
    synthetic_dir, tmp_path, inbox, clock
):  # type: ignore[no-untyped-def]
    texts = ingested_texts(synthetic_dir, tmp_path, inbox, clock)
    message, text = next((m, t) for m, t in texts if "New ETD" in t)
    anchor = message.sent_at.date()
    assert anchor == date(2026, 9, 29)
    assert [d.start for d in find_dates(text, anchor)] == [date(2026, 10, 6), date(2026, 10, 22)]
    bookings = {
        (m.value, m.qualifier) for m in find_references(text) if m.kind is ReferenceKind.BOOKING
    }
    assert bookings == {("990000203", None), ("990000202", "previous")}


def test_the_booking_confirmation_gives_ports_dates_and_equipment(
    synthetic_dir, tmp_path, inbox, clock
):  # type: ignore[no-untyped-def]
    texts = ingested_texts(synthetic_dir, tmp_path, inbox, clock)
    _, text = next((m, t) for m, t in texts if "Port of discharge: NEW YORK" in t)
    assert [(p.unlocode, p.role) for p in find_locations(text)] == [
        ("ESVLC", "POL"),
        ("USNYC", "POD"),
    ]
    (equipment,) = find_equipment(text)
    assert (equipment.count, equipment.iso_type) == (1, "45G1")
    dates = find_dates(text, date(2026, 9, 20))
    assert [(d.start.isoformat(), d.at.isoformat() if d.at else None) for d in dates] == [
        ("2026-10-08", None),
        ("2026-10-24", None),
        ("2026-10-05", "12:00:00"),
        ("2026-10-06", "12:00:00"),
    ]
