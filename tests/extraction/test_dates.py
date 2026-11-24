from datetime import date, time

import pytest

from eshipping_ai.domain.vocabulary import TimePrecision
from eshipping_ai.extraction.dates import find_dates

ANCHOR = date(2026, 9, 20)


def one(text: str, **kwargs):  # type: ignore[no-untyped-def]
    found = find_dates(text, ANCHOR, **kwargs)
    assert len(found) == 1, found
    return found[0]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ETD 08/10/2026", date(2026, 10, 8)),
        ("26.08.2026", date(2026, 8, 26)),
        ("9 de octubre de 2026", date(2026, 10, 9)),
        ("Oct 9, 2026", date(2026, 10, 9)),
        ("9th October 2026", date(2026, 10, 9)),
        ("el 5 sep. 2026", date(2026, 9, 5)),
        ("12/25/2026", date(2026, 12, 25)),
        ("25/12/26", date(2026, 12, 25)),
    ],
)
def test_formats(text: str, expected: date) -> None:
    mention = one(text)
    assert mention.start == expected
    assert not mention.year_inferred


def test_missing_year_is_inferred_from_the_message_date() -> None:
    mention = one("ETD 22/09")
    assert (mention.start, mention.year_inferred, mention.ambiguous) == (
        date(2026, 9, 22),
        True,
        False,
    )
    assert one("ETA 15/01").start == date(2027, 1, 15)
    assert one("salió el 05/08").start == date(2026, 8, 5)


def test_a_date_far_from_the_window_is_flagged() -> None:
    assert one("el 10/07").ambiguous


def test_day_month_is_the_default_and_is_flagged_when_it_could_be_either() -> None:
    mention = one("ETD 09/10/2026")
    assert (mention.start, mention.ambiguous) == (date(2026, 10, 9), True)
    assert not one("ETD 29/10/2026").ambiguous
    assert not one("ETD 09/09/2026").ambiguous


def test_sender_profile_fixes_the_order() -> None:
    assert one("09/10/2026", month_first=False).start == date(2026, 10, 9)
    assert not one("09/10/2026", month_first=False).ambiguous
    assert one("09/10/2026", month_first=True).start == date(2026, 9, 10)


def test_time_and_precision() -> None:
    mention = one("closing 16/09/2026 a las 10:30")
    assert (mention.at, mention.precision) == (time(10, 30), TimePrecision.DATETIME)
    assert one("ETD 22/09/2026 at 17:05").at == time(17, 5)
    assert one("ETD 22/09/2026").precision is TimePrecision.DATE


def test_ranges_keep_both_ends() -> None:
    mention = one("ventana de carga del 29/09/2026 al 30/09/2026")
    assert (mention.start, mention.end, mention.precision) == (
        date(2026, 9, 29),
        date(2026, 9, 30),
        TimePrecision.RANGE,
    )
    assert one("29/07/2026 \u2013 03/08/2026").end == date(2026, 8, 3)
    assert one("from 29/09/2026 to 02/10/2026").end == date(2026, 10, 2)
    year_end = one("del 28/12 al 03/01")
    assert (year_end.start, year_end.end) == (date(2026, 12, 28), date(2027, 1, 3))


def test_approximate_dates() -> None:
    assert one("la ETA es sobre el 27/10").precision is TimePrecision.APPROX
    assert one("ETA approx. 27/10").precision is TimePrecision.APPROX


def test_relative_words_use_the_message_date() -> None:
    mention = one("lo cargamos mañana")
    assert (mention.start, mention.relative) == (date(2026, 9, 21), True)
    assert one("sailed yesterday").start == date(2026, 9, 19)


@pytest.mark.parametrize(
    "text", ["Peso 22.890 kg", "30/02/2026", "pedido 1234", "1.5 toneladas", "ETA 40/50"]
)
def test_non_dates_are_ignored(text: str) -> None:
    assert find_dates(text, ANCHOR) == []


def test_several_dates_in_order_without_overlaps() -> None:
    found = find_dates("ETD 29/09/2026, ETA 05/11/2026 y levante el 06/10/2026 10:00", ANCHOR)
    assert [m.start for m in found] == [date(2026, 9, 29), date(2026, 11, 5), date(2026, 10, 6)]
    assert found[2].at == time(10, 0)
