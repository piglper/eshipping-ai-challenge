"""Deterministic extraction of dates, with their precision (RF-21, RF-22, RF-40).

The extractor never invents certainty: a date that could be read as day-month or
month-day is flagged ambiguous (A-09), a missing year is inferred from the date of the
message and flagged (A-07), a range keeps both ends (A-05) and an approximate date says so
(A-06). Day-month is the default order; a sender profile can switch it. Time zones are not
applied here: they depend on the place of the event and are added when the value is
normalised (A-11).
"""

import re
from dataclasses import dataclass
from datetime import date, time, timedelta

from eshipping_ai.domain.vocabulary import TimePrecision
from eshipping_ai.extraction.thread import MONTHS

MAX_MONTH = 12
YEAR_WINDOW_BEFORE = timedelta(days=60)
YEAR_WINDOW_AFTER = timedelta(days=180)
_TWO_DIGIT_YEAR_BASE = 2000
_APPROX_LOOKBACK = 18
_ADJACENT_GAP = 3
"""A relative word right before an explicit date ("hoy 22/09") is only a label of it."""

_TIME = r"(?:(?:\s+a\s+las|\s+at|\s*,|\s+)\s*(?P<{p}h>[01]?\d|2[0-3]):(?P<{p}min>[0-5]\d))?"
_NUMERIC = (
    r"(?<![\d/.])(?P<{p}d>\d{{1,2}})(?:"
    r"(?P<{p}sep>/)(?P<{p}m>\d{{1,2}})(?:/(?P<{p}y>\d{{4}}|\d{{2}}))?"
    r"|(?P<{p}dsep>[.\-])(?P<{p}dm>\d{{1,2}})(?P=_dsep)(?P<{p}dy>\d{{4}}|\d{{2}}))(?![\d/])"
)
_MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
_DAY_FIRST = (
    r"(?<![\d/])(?P<{p}xd>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:de\s+)?(?P<{p}xm>"
    + _MONTH_NAMES
    + r")\b\.?"
    r"(?:\s+(?:de\s+)?(?P<{p}xy>\d{{4}}))?"
)
_MONTH_FIRST = (
    r"\b(?P<{p}ym>" + _MONTH_NAMES + r")\b\.?\s+(?P<{p}yd>\d{{1,2}})(?:st|nd|rd|th)?\b"
    r"(?!\s*[:/])(?:,?\s+(?P<{p}yy>\d{{4}}))?"
)
_APPROX_RE = re.compile(
    r"(?:sobre(?: el)?|hacia(?: el)?|around|about|approx(?:imately|\.)?|aprox(?:\.|imadamente)?"
    r"|circa|~)\s*$",
    re.IGNORECASE,
)
_RELATIVE_RE = re.compile(r"\b(?P<word>hoy|mañana|ayer|today|tomorrow|yesterday)\b", re.IGNORECASE)
_RELATIVE_DAYS = {
    "hoy": 0,
    "today": 0,
    "mañana": 1,
    "tomorrow": 1,
    "ayer": -1,
    "yesterday": -1,
}
_RANGE_SEP = r"\s*(?:-|\u2013|\u2014|\bal?\b|\bto\b|\buntil\b|\bhasta(?: el)?\b)\s*"


@dataclass(frozen=True, slots=True)
class DateMention:
    """A date, or a range of dates, found in a text.

    ``end`` is set only for ranges. ``ambiguous`` means that the order of day and month, or
    the year, could not be settled from the text; the value is the most likely reading.
    ``relative`` marks words such as "mañana", resolved against the date of the message.
    """

    start: date
    end: date | None
    at: time | None
    precision: TimePrecision
    ambiguous: bool
    year_inferred: bool
    relative: bool
    raw: str
    span_start: int
    span_end: int


def _infer_year(day: int, month: int, anchor: date) -> tuple[int, bool] | None:
    """Pick the year that puts the date closest to the anchor (A-07).

    Returns:
        The year and whether it falls inside the expected window; None if the date does
        not exist in any nearby year.
    """
    candidates: list[date] = []
    for year in (anchor.year - 1, anchor.year, anchor.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    if not candidates:
        return None
    best = min(candidates, key=lambda candidate: abs((candidate - anchor).days))
    inside = anchor - YEAR_WINDOW_BEFORE <= best <= anchor + YEAR_WINDOW_AFTER
    return best.year, inside


def _resolve_numeric(
    first: int, second: int, year: str | None, anchor: date, *, month_first: bool | None
) -> tuple[date, bool, bool] | None:
    """Resolve the two numbers of a numeric date.

    Returns:
        The date, whether it is ambiguous and whether the year was inferred; None if no
        reading is a valid date.
    """
    day, month = (second, first) if month_first else (first, second)
    ambiguous = (
        month_first is None and first != second and first <= MAX_MONTH and second <= MAX_MONTH
    )
    if month > MAX_MONTH and day <= MAX_MONTH:
        day, month, ambiguous = month, day, False
    elif day > MAX_MONTH and month <= MAX_MONTH:
        ambiguous = False
    if not 1 <= month <= MAX_MONTH:
        return None
    if year is not None:
        full = int(year) if len(year) == 4 else _TWO_DIGIT_YEAR_BASE + int(year)  # noqa: PLR2004
        try:
            return date(full, month, day), ambiguous, False
        except ValueError:
            return None
    inferred = _infer_year(day, month, anchor)
    if inferred is None:
        return None
    resolved_year, inside = inferred
    return date(resolved_year, month, day), ambiguous or not inside, True


def _token(prefix: str) -> str:
    """Regex for one date token; named groups carry ``prefix`` so two can share a pattern."""
    parts = (_NUMERIC.replace("(?P=_dsep)", f"(?P={prefix}dsep)"), _DAY_FIRST, _MONTH_FIRST)
    return "(?:" + "|".join(part.format(p=prefix) for part in parts) + ")"


_TOKEN = _token("a_")
_TOKEN_END = _token("b_")
_SINGLE_RE = re.compile(_TOKEN + _TIME.format(p="a_"), re.IGNORECASE)
_RANGE_RE = re.compile(_TOKEN + _RANGE_SEP + _TOKEN_END, re.IGNORECASE)


def _read_token(
    match: re.Match[str], prefix: str, anchor: date, *, month_first: bool | None
) -> tuple[date, bool, bool] | None:
    """Read the date held by the groups with a given prefix."""
    g = match.groupdict()
    if g[f"{prefix}d"] is not None:
        if g[f"{prefix}sep"] == "/":
            return _resolve_numeric(
                int(g[f"{prefix}d"]),
                int(g[f"{prefix}m"]),
                g[f"{prefix}y"],
                anchor,
                month_first=month_first,
            )
        return _resolve_numeric(
            int(g[f"{prefix}d"]),
            int(g[f"{prefix}dm"]),
            g[f"{prefix}dy"],
            anchor,
            month_first=month_first,
        )
    if g[f"{prefix}xd"] is not None:
        day, month, year = g[f"{prefix}xd"], MONTHS[g[f"{prefix}xm"].lower()], g[f"{prefix}xy"]
    else:
        day, month, year = g[f"{prefix}yd"], MONTHS[g[f"{prefix}ym"].lower()], g[f"{prefix}yy"]
    if year is not None:
        try:
            return date(int(year), month, int(day)), False, False
        except ValueError:
            return None
    inferred = _infer_year(int(day), month, anchor)
    if inferred is None:
        return None
    resolved_year, inside = inferred
    return date(resolved_year, month, int(day)), not inside, True


def find_dates(text: str, anchor: date, *, month_first: bool | None = None) -> list[DateMention]:
    """Find the dates and date ranges of a text.

    Args:
        text: Text to search.
        anchor: Date of the message that contains the text; used for missing years and for
            relative words such as "mañana" (A-10).
        month_first: Order of the numbers in ``09/10`` when the sender profile says it:
            True for month-day, False for day-month. None (unknown) reads day-month and
            flags as ambiguous every date whose two numbers could be either (A-09).

    Returns:
        The mentions in order of appearance; overlapping readings are resolved in favour of
        ranges and then of dates with a year.
    """
    mentions: list[DateMention] = []
    taken: list[tuple[int, int]] = []

    def free(start: int, end: int) -> bool:
        return all(end <= other_start or start >= other_end for other_start, other_end in taken)

    for match in _RANGE_RE.finditer(text):
        first = _read_token(match, "a_", anchor, month_first=month_first)
        last = _read_token(match, "b_", anchor, month_first=month_first)
        if first is None or last is None or not free(*match.span()):
            continue
        start, end = first[0], last[0]
        if last[2] and not first[2]:
            end = _same_year_or_next(end, start)
        if end <= start:
            continue
        taken.append(match.span())
        mentions.append(
            DateMention(
                start,
                end,
                None,
                TimePrecision.RANGE,
                first[1] or last[1],
                first[2] or last[2],
                relative=False,
                raw=match.group(0),
                span_start=match.start(),
                span_end=match.end(),
            )
        )
    for match in _SINGLE_RE.finditer(text):
        if not free(*match.span()):
            continue
        read = _read_token(match, "a_", anchor, month_first=month_first)
        if read is None:
            continue
        taken.append(match.span())
        moment = time(int(match["a_h"]), int(match["a_min"])) if match["a_h"] is not None else None
        approx = _APPROX_RE.search(text[max(0, match.start() - _APPROX_LOOKBACK) : match.start()])
        precision = (
            TimePrecision.APPROX
            if approx
            else TimePrecision.DATETIME
            if moment is not None
            else TimePrecision.DATE
        )
        mentions.append(
            DateMention(
                read[0],
                None,
                moment,
                precision,
                read[1],
                read[2],
                relative=False,
                raw=match.group(0),
                span_start=match.start(),
                span_end=match.end(),
            )
        )
    for match in _RELATIVE_RE.finditer(text):
        if free(*match.span()):
            resolved = anchor + timedelta(days=_RELATIVE_DAYS[match["word"].lower()])
            mentions.append(
                DateMention(
                    resolved,
                    None,
                    None,
                    TimePrecision.DATE,
                    False,
                    False,
                    relative=True,
                    raw=match.group(0),
                    span_start=match.start(),
                    span_end=match.end(),
                )
            )
    ordered = sorted(mentions, key=lambda mention: mention.span_start)
    return [
        mention
        for index, mention in enumerate(ordered)
        if not (
            mention.relative
            and index + 1 < len(ordered)
            and ordered[index + 1].span_start - mention.span_end <= _ADJACENT_GAP
        )
    ]


def _same_year_or_next(end: date, start: date) -> date:
    """Move an end date without year to the next year if it would fall before the start."""
    if end >= start:
        return end
    try:
        return end.replace(year=end.year + 1)
    except ValueError:
        return end
