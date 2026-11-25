"""Properties of the deterministic extractors, checked on generated inputs.

Mails are free text written by people: the extractors must never break on any text and
every mention they return must point at the exact characters it cites as evidence.
"""

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from eshipping_ai.domain.identifiers import (
    is_valid_container_number,
    iso6346_check_digit,
    normalize_reference,
)
from eshipping_ai.extraction.dates import find_dates
from eshipping_ai.extraction.equipment import find_equipment
from eshipping_ai.extraction.locations import find_locations
from eshipping_ai.extraction.references import ReferenceKind, find_references

# Text close to that of a shipping mail, so that the generator reaches the patterns often.
_PIECES = st.sampled_from(
    [
        "ETD ",
        "ETA ",
        "Vessel ",
        "booking ",
        "B/L ",
        "Contenedor ",
        "cut-off ",
        " - ",
        "/",
        ".",
        ", ",
        "\n",
        "de octubre de ",
        "Oct ",
        "mañana",
        "Valencia",
        "ESVLC",
        "2x40HC",
        "20DV",
        "MSCU",
        "ES2690",
    ]
)
_MAIL_TEXT = st.lists(
    st.one_of(_PIECES, st.integers(0, 99999).map(str), st.text(max_size=8)), max_size=30
).map("".join)
_ANCHORS = st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31))
_OWNER = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=3, max_size=3)
_CATEGORY = st.sampled_from("UJZR")
_SERIAL = st.integers(0, 999_999).map(lambda n: f"{n:06d}")


@st.composite
def _containers(draw: st.DrawFn) -> str:
    prefix = draw(_OWNER) + draw(_CATEGORY) + draw(_SERIAL)
    return prefix + str(iso6346_check_digit(prefix))


@given(_containers())
def test_a_container_with_its_check_digit_is_valid(number: str) -> None:
    assert is_valid_container_number(number)
    found = find_references(f"Contenedor {number} cargado")
    assert [(m.kind, m.value, m.valid) for m in found] == [(ReferenceKind.CONTAINER, number, True)]


@given(_containers(), st.integers(1, 9))
def test_a_wrong_check_digit_is_always_caught(number: str, shift: int) -> None:
    wrong = number[:-1] + str((int(number[-1]) + shift) % 10)
    assert not is_valid_container_number(wrong)


@given(st.text(max_size=40))
def test_normalizing_a_reference_twice_changes_nothing(raw: str) -> None:
    once = normalize_reference(raw)
    assert normalize_reference(once) == once


@given(_MAIL_TEXT, _ANCHORS, st.sampled_from([None, True, False]))
def test_dates_point_at_their_evidence_and_do_not_overlap(
    text: str, anchor: date, month_first: bool | None
) -> None:
    mentions = find_dates(text, anchor, month_first=month_first)
    previous_end = 0
    for mention in mentions:
        assert text[mention.span_start : mention.span_end] == mention.raw
        assert mention.span_start >= previous_end
        assert mention.end is None or mention.end > mention.start
        previous_end = mention.span_end


@given(st.dates(min_value=date(2000, 1, 1), max_value=date(2099, 12, 31)), _ANCHORS)
def test_a_full_date_is_read_as_written(day: date, anchor: date) -> None:
    (mention,) = find_dates(f"ETA {day:%d/%m/%Y}", anchor, month_first=False)
    assert (mention.start, mention.ambiguous, mention.year_inferred) == (day, False, False)


@given(_ANCHORS, st.integers(-200, 300))
def test_a_date_without_year_falls_next_to_the_message(anchor: date, offset: int) -> None:
    day = anchor + timedelta(days=offset)
    if (day.month, day.day) == (2, 29):
        return
    (mention,) = find_dates(f"ETA {day:%d/%m}", anchor, month_first=False)
    assert mention.year_inferred
    assert abs((mention.start - anchor).days) <= abs(offset)


@given(_MAIL_TEXT)
def test_identifiers_ports_and_equipment_point_at_their_evidence(text: str) -> None:
    for found in (find_references(text), find_locations(text), find_equipment(text)):
        for mention in found:
            assert text[mention.start : mention.end] == mention.raw
