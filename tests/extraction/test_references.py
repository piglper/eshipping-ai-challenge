import pytest

from eshipping_ai.extraction.references import (
    ReferenceKind,
    find_bills_of_lading,
    find_bookings,
    find_containers,
    find_operations,
    find_references,
)

# SYNU1000019 and SYNU3000039 are invented containers with a valid ISO 6346 check digit.


def values(mentions):  # type: ignore[no-untyped-def]
    return [m.value for m in mentions]


def test_containers_are_validated_and_normalised() -> None:
    text = "Contenedor: SYNU1000019 (40HC) y syn u 300003-9 y SYNU1000018"
    found = find_containers(text.replace("syn u 300003-9", "SYNU 300003-9"))
    assert values(found) == ["SYNU1000019", "SYNU3000039", "SYNU1000018"]
    assert [m.valid for m in found] == [True, True, False]
    assert text[found[0].start : found[0].end] == "SYNU1000019"


def test_a_seal_that_looks_like_a_container_is_skipped() -> None:
    assert find_containers("Precinto: ABCU1234567, contenedor SYNU1000019") != []
    found = find_containers("Seal no. ABCU1234567 / Precinto ABCU7654321 / SYNU1000019")
    assert values(found) == ["SYNU1000019"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("BOOKING CONFIRMATION 990000101 - AURORA", ["990000101"]),
        ("Booking number: 990000101", ["990000101"]),
        ("BKG=ABCD1234567 VOY=041E", ["ABCD1234567"]),
        ("Reserva nº 990000505", ["990000505"]),
        ("Pedido 990000101 de la fábrica", []),
        ("Llamar al 912345678", []),
        ("booking 123", []),
    ],
)
def test_bookings_need_context(text: str, expected: list[str]) -> None:
    assert values(find_bookings(text)) == expected


def test_a_replaced_booking_is_marked_as_previous() -> None:
    found = find_bookings("New booking number: 990000203 (replaces 990000202)")
    assert [(m.value, m.qualifier) for m in found] == [
        ("990000203", None),
        ("990000202", "previous"),
    ]


def test_operations_complete_and_truncated() -> None:
    found = find_operations("Expediente ES26900001 y Exp. ES1234; no ES269000012")
    assert [(m.kind, m.value, m.valid) for m in found] == [
        (ReferenceKind.OPERATION, "ES26900001", True),
        (ReferenceKind.OPERATION_PREFIX, "ES1234", False),
    ]


def test_bills_of_lading_need_context_and_a_digit() -> None:
    assert values(find_bills_of_lading("B/L number: NFLX123456789 listo")) == ["NFLX123456789"]
    assert values(find_bills_of_lading("SWB: ABCD123456")) == ["ABCD123456"]
    assert find_bills_of_lading("BL DRAFT enviado") == []
    assert find_bills_of_lading("Master plan de trabajo") == []


def test_find_references_returns_everything_in_order() -> None:
    text = "ES26900001 booking 990000101 contenedor SYNU1000019"
    assert [m.kind for m in find_references(text)] == [
        ReferenceKind.OPERATION,
        ReferenceKind.BOOKING,
        ReferenceKind.CONTAINER,
    ]
