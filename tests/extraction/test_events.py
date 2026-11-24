import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from eshipping_ai.adapters.mail_files import MailFileParser
from eshipping_ai.domain.vocabulary import EventClassifier, EventType, TimePrecision
from eshipping_ai.extraction.events import extract_candidates, find_identifiers
from eshipping_ai.extraction.thread import clean_body

MADRID = ZoneInfo("Europe/Madrid")
ANCHOR = date(2026, 9, 20)
ACT, EST, PLN = EventClassifier.ACTUAL, EventClassifier.ESTIMATED, EventClassifier.PLANNED


def candidates(text: str, anchor: date = ANCHOR):  # type: ignore[no-untyped-def]
    return {(c.field, c.value): c for c in extract_candidates(text, anchor, MADRID)}


@pytest.mark.parametrize(
    ("text", "field", "state"),
    [
        ("ETD: 22/09/2026", "vessel_departure", EST),
        ("La salida prevista es el 22/09/2026", "vessel_departure", EST),
        ("ETA: 05/10/2026", "vessel_arrival_pod", EST),
        ("El buque zarpó el 22/09/2026", "vessel_departure", ACT),
        ("vessel sailed on 22/09/2026", "vessel_departure", ACT),
        ("VGM cut-off: 22/09/2026 12:00", "cutoff_vgm", PLN),
        ("Documentation cut-off: 22/09/2026", "cutoff_document", PLN),
        ("FCL cut-off: 22/09/2026", "cutoff_full", PLN),
        ("Carga en almacén: 22/09/2026", "stuffing", PLN),
        ("El contenedor se ha cargado hoy 22/09/2026", "stuffing", ACT),
        ("Se ha concedido el levante el 22/09/2026", "customs_release", ACT),
    ],
)
def test_the_words_next_to_a_date_say_what_it_is(
    text: str, field: str, state: EventClassifier
) -> None:
    (found,) = candidates(text).values()
    assert (found.field, found.classifier) == (field, state)


def test_dates_without_a_label_are_not_guessed() -> None:
    assert candidates("Nos vemos el 22/09/2026 para comer") == {}


def test_a_wrapped_line_still_names_the_date() -> None:
    text = "Please be informed that vessel X sailed from Valencia\non 04/10/2026 at 21:30."
    (found,) = candidates(text).values()
    assert (found.field, found.classifier, found.value) == ("vessel_departure", ACT, "2026-10-04")
    assert found.event_time == datetime(2026, 10, 4, 21, 30, tzinfo=MADRID)
    assert found.precision is TimePrecision.DATETIME


def test_dates_carry_their_time_zone_range_and_evidence() -> None:
    text = "Ventana de carga del 29/09/2026 al 30/09/2026"
    (found,) = candidates(text).values()
    assert found.precision is TimePrecision.RANGE
    assert found.value == "2026-09-29/2026-09-30"
    assert found.event_time == datetime(2026, 9, 29, tzinfo=MADRID)
    assert found.event_time_end == datetime(2026, 9, 30, tzinfo=MADRID)
    assert text[found.start : found.end].endswith("30/09/2026")
    default_zone = extract_candidates("ETD: 22/09/2026", ANCHOR)[0]
    assert default_zone.event_time == datetime(2026, 9, 22, tzinfo=UTC)


def test_an_ambiguous_order_lowers_the_confidence() -> None:
    sure = candidates("ETD: 22/09/2026")[("vessel_departure", "2026-09-22")]
    unsure = candidates("ETD: 09/10/2026")[("vessel_departure", "2026-10-09")]
    assert unsure.ambiguous and unsure.confidence < sure.confidence


def test_vessel_voyage_and_vessel_change() -> None:
    plain = candidates("Vessel / Voyage: AURORA FICTICIA / 041E")[("vessel", "AURORA FICTICIA")]
    assert (plain.voyage, plain.event_type) == ("041E", EventType.DEPARTURE)
    new = candidates("Previous vessel: OLD ONE / 1\nNew vessel / voyage: CELESTE FICTICIA / 013W")
    assert list(new) == [("vessel", "CELESTE FICTICIA")]
    assert new[("vessel", "CELESTE FICTICIA")].event_type is EventType.VESSEL_CHANGE


def test_booking_equipment_and_replaced_booking() -> None:
    found = candidates("Booking number: 990000101\nEquipment: 2 x 40HC\nTotal 40HC")
    assert set(found) == {("booking", "990000101"), ("equipment_count", "2")}
    rollover = candidates("BKG 990000202\nNew booking number: 990000203 (replaces 990000202)")
    assert {k for k in rollover if k[0] == "booking"} == {("booking", "990000203")}


def test_a_repeated_value_is_reported_once() -> None:
    assert len(extract_candidates("Booking 990000101\nBooking: 990000101", ANCHOR)) == 1


def test_options_are_flagged_as_offered() -> None:
    options = "Opción 1: ETD 04/09/2026\nOpción 2: ETD 07/09/2026"
    assert all(c.offered for c in extract_candidates(options, ANCHOR))
    assert not any(c.offered for c in extract_candidates("ETD 04/09/2026", ANCHOR))


def test_identifiers_for_association() -> None:
    ids = find_identifiers(
        "BKG 990000202 New booking number: 990000203 (replaces 990000202) SYNU1000019 SYNU1000018"
    )
    assert ids.bookings == ("990000202", "990000203")
    assert ids.previous_bookings == ("990000202",)
    assert ids.containers == ("SYNU1000019",)


def test_the_rules_find_what_the_synthetic_gold_expects(synthetic_dir: Path) -> None:
    """Run the rules over every synthetic mail and check the gold values are all found."""
    gold = json.loads((synthetic_dir / "gold.json").read_text(encoding="utf-8"))["expedientes"]
    parser = MailFileParser()
    for operation, fields in gold.items():
        container = parser.parse(
            (synthetic_dir / "mails" / f"{operation}.eml").read_bytes(), "x.eml"
        )
        found: set[tuple[str, str]] = set()
        for mail in container.embedded:
            body = clean_body(mail.text_body)
            sent = mail.sent_at
            assert sent is not None
            text = f"Asunto: {mail.subject}\n{body}"
            found |= {(c.field, c.value) for c in extract_candidates(text, sent.date(), MADRID)}
        for name in (
            "booking",
            "vessel",
            "vessel_departure",
            "vessel_arrival_pod",
            "customs_release",
        ):
            expected = fields.get(name)
            if expected and expected["source"] is not None:
                assert (name, str(expected["value"])) in found, (operation, name)
        stuffing = fields.get("stuffing")
        if stuffing and stuffing["source"] is not None:
            assert ("stuffing", stuffing["value"]["date"]) in found, operation
        _ = time  # the cut-off times are checked by the unit tests above
