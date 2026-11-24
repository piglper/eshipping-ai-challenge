"""From findings to candidate observations, with rules (RF-20 to RF-23, RF-40, RF-41).

A date alone says nothing; what makes it the departure, the arrival or a cut-off is the
words next to it on the same line (``ETD``, ``llegada``, ``VGM cut-off``). The state of the
information (planned, estimated or actual, A-02) comes from the vocabulary of the line:
"sailed" and "se ha cargado" are actual, "ETD" and "prevista" are estimates, a loading
window is a plan. When the rules cannot say, no candidate is produced: what is left is for
the next tier of the cascade (ADR-0008), never a guess.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, tzinfo

from eshipping_ai.domain.vocabulary import EventClassifier, EventType, TimePrecision
from eshipping_ai.extraction.classify import lists_offered_options
from eshipping_ai.extraction.dates import DateMention, find_dates
from eshipping_ai.extraction.equipment import find_equipment
from eshipping_ai.extraction.locations import strip_accents
from eshipping_ai.extraction.references import (
    find_bills_of_lading,
    find_bookings,
    find_containers,
    find_operations,
)

_LABEL_LOOKBACK = 64
_UNCERTAIN_ORDER_PENALTY = 0.25
_BASE_CONFIDENCE = 0.97
_ACTUAL_WORDS = (
    "zarp",
    "sailed",
    "salio",
    "departed",
    "se ha cargado",
    "se cargo",
    "cargado hoy",
    "loaded",
    "arrived",
    "llego",
    "concedido",
    "granted",
    "released",
)
_ESTIMATE_WORDS = ("prevista", "previsto", "estimated", "expected", "eta", "etd", "aprox")
_PLAN_WORDS = ("ventana", "window", "programad", "scheduled", "plan")

# (field, event, regex on the label, default state). Order matters: the first match wins.
_RULES: tuple[tuple[str, EventType, str, EventClassifier], ...] = (
    ("cutoff_vgm", EventType.VGM_CUTOFF, r"\bvgm\b", EventClassifier.PLANNED),
    (
        "cutoff_document",
        EventType.DOCUMENT_CUTOFF,
        r"documentation|documental|doc(?:s)?\.? (?:cut|closing)|\bsi cut",
        EventClassifier.PLANNED,
    ),
    (
        "cutoff_full",
        EventType.FULL_CONTAINER_CUTOFF,
        r"cut[- ]?off|closing|\bfcl\b|entrega en terminal|terminal delivery",
        EventClassifier.PLANNED,
    ),
    (
        "stuffing",
        EventType.STUFFING,
        r"carga|loading date|stuffing|pick[- ]?up",
        EventClassifier.PLANNED,
    ),
    (
        "customs_release",
        EventType.CUSTOMS_RELEASED,
        r"levante|customs release|despacho",
        EventClassifier.ACTUAL,
    ),
    (
        "vessel_departure",
        EventType.DEPARTURE,
        r"\betd\b|salida|departure|sail|zarp|\bsale\b|\bsalio\b",
        EventClassifier.ESTIMATED,
    ),
    (
        "vessel_arrival_pod",
        EventType.ARRIVAL,
        r"\beta\b|llegada|arrival|arriv|\bllega\b|\bllego\b",
        EventClassifier.ESTIMATED,
    ),
)
_COMPILED_RULES = tuple(
    (field, event, re.compile(pattern), state) for field, event, pattern, state in _RULES
)
_VESSEL_LINE_RE = re.compile(
    r"^\W*(?P<label>(?:new\s+|nuevo\s+|previous\s+|anterior\s+)?(?:vessel|buque|barco)\b[^:=\n]*)"
    r"[:=]\s*(?P<name>[^/\n(]+?)\s*(?:/\s*(?P<voyage>[A-Za-z0-9]{2,8}))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_VESSEL_CHANGE_WORDS = ("new", "nuevo", "cambio")
_PREVIOUS_WORDS = ("previous", "anterior")


@dataclass(frozen=True, slots=True)
class Candidate:
    """A value found by the rules, ready to become an observation.

    ``start`` and ``end`` delimit the evidence, the literal fragment that supports it.
    ``date_end``, ``at`` and ``precision`` are set for dates. ``offered`` marks values that
    come from a list of options that has not been confirmed (A-25).
    """

    field: str
    event_type: EventType
    classifier: EventClassifier
    value: str
    value_raw: str
    start: int
    end: int
    confidence: float
    event_time: datetime | None = None
    event_time_end: datetime | None = None
    precision: TimePrecision | None = None
    voyage: str | None = None
    offered: bool = False
    ambiguous: bool = False


def _line_bounds(text: str, position: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, position) + 1
    end = text.find("\n", position)
    return start, len(text) if end == -1 else end


def _classifier(label: str, line: str, default: EventClassifier) -> EventClassifier:
    """State of the information from the vocabulary of the line (A-02)."""
    if any(word in line for word in _ACTUAL_WORDS):
        return EventClassifier.ACTUAL
    if default is EventClassifier.PLANNED and any(word in label for word in _ESTIMATE_WORDS):
        return EventClassifier.ESTIMATED
    if default is EventClassifier.ESTIMATED and any(word in line for word in _PLAN_WORDS):
        return EventClassifier.PLANNED
    return default


def _word_start(text: str, start: int, limit: int) -> int:
    """Move a start that fell in the middle of a word to the beginning of the next one."""
    if start == 0 or text[start - 1].isspace():
        return start
    following = text.find(" ", start, limit)
    return start if following == -1 else following + 1


def _moment(day: date, at: time | None, tz: tzinfo) -> datetime:
    return datetime.combine(day, at or time(0), tzinfo=tz)


def _first_rule(label: str) -> tuple[str, EventType, EventClassifier] | None:
    for field, event, pattern, default in _COMPILED_RULES:
        if pattern.search(label):
            return field, event, default
    return None


def _date_candidate(
    mention: DateMention, text: str, plain: str, tz: tzinfo, *, offered: bool
) -> Candidate | None:
    line_start, line_end = _line_bounds(text, mention.span_start)
    label_start = max(line_start, mention.span_start - _LABEL_LOOKBACK)
    rule = _first_rule(plain[label_start : mention.span_start])
    if rule is None and line_start > 0:
        # Mail clients wrap long lines: the words that name the date may end the previous one.
        line_start, _ = _line_bounds(text, line_start - 1)
        label_start = max(line_start, label_start - _LABEL_LOOKBACK)
        rule = _first_rule(plain[label_start : mention.span_start])
    if rule is None:
        return None
    field, event, default = rule
    label = plain[label_start : mention.span_start]
    confidence = _BASE_CONFIDENCE - (_UNCERTAIN_ORDER_PENALTY if mention.ambiguous else 0)
    value = mention.start.isoformat()
    if mention.end is not None:
        value = f"{value}/{mention.end.isoformat()}"
    return Candidate(
        field=field,
        event_type=event,
        classifier=_classifier(label, plain[line_start:line_end], default),
        value=value,
        value_raw=mention.raw,
        start=_word_start(text, label_start, mention.span_start),
        end=mention.span_end,
        confidence=confidence,
        event_time=_moment(mention.start, mention.at, tz),
        event_time_end=_moment(mention.end, None, tz) if mention.end else None,
        precision=mention.precision,
        offered=offered,
        ambiguous=mention.ambiguous,
    )


def _vessel_candidates(text: str, *, offered: bool) -> list[Candidate]:
    found = []
    for match in _VESSEL_LINE_RE.finditer(text):
        label = match["label"].lower()
        if any(word in label for word in _PREVIOUS_WORDS):
            continue
        name = " ".join(match["name"].upper().split())
        if len(name) < 3 or name.isdigit():  # noqa: PLR2004 - a vessel name has some letters
            continue
        changed = any(word in label for word in _VESSEL_CHANGE_WORDS)
        found.append(
            Candidate(
                field="vessel",
                event_type=EventType.VESSEL_CHANGE if changed else EventType.DEPARTURE,
                classifier=EventClassifier.ESTIMATED,
                value=name,
                value_raw=match["name"].strip(),
                start=match.start("label"),
                end=match.end("name"),
                confidence=_BASE_CONFIDENCE,
                voyage=(match["voyage"] or "").upper() or None,
                offered=offered,
            )
        )
    return found


def _has_explicit_count(raw: str) -> bool:
    """``2 x 40HC`` states a count; a bare ``40HC`` does not."""
    return re.match(r"\s*\d+\s*[x\u00d7]", raw, re.IGNORECASE) is not None


def extract_candidates(
    text: str, anchor: date, tz: tzinfo = UTC, *, month_first: bool | None = None
) -> list[Candidate]:
    """Find the candidate observations of a message.

    Args:
        text: Text of the message, subject included.
        anchor: Date of the message, for years and relative words.
        tz: Time zone of the place of the events (A-11), applied to every moment.
        month_first: Date order of the sender, if its profile says it (RF-73).

    Returns:
        The candidates in order of appearance. Containers and previous bookings are not
        candidates: they are identifiers used for association (see ``find_identifiers``).
    """
    plain = strip_accents(text)
    offered = lists_offered_options(text)
    candidates = [
        found
        for mention in find_dates(text, anchor, month_first=month_first)
        if (found := _date_candidate(mention, text, plain, tz, offered=offered))
    ]
    candidates += _vessel_candidates(text, offered=offered)
    replaced = {b.value for b in find_bookings(text) if b.qualifier == "previous"}
    for booking in find_bookings(text):
        if booking.qualifier is None and booking.value not in replaced:
            candidates.append(
                Candidate(
                    field="booking",
                    event_type=EventType.BOOKING_CONFIRMED,
                    classifier=EventClassifier.ESTIMATED,
                    value=booking.value,
                    value_raw=booking.raw,
                    start=booking.start,
                    end=booking.end,
                    confidence=_BASE_CONFIDENCE,
                )
            )
    equipment = [m for m in find_equipment(text) if _has_explicit_count(m.raw)]
    if len(equipment) == 1:
        mention = equipment[0]
        candidates.append(
            Candidate(
                field="equipment_count",
                event_type=EventType.BOOKING_CONFIRMED,
                classifier=EventClassifier.ESTIMATED,
                value=str(mention.count),
                value_raw=mention.raw,
                start=mention.start,
                end=mention.end,
                confidence=_BASE_CONFIDENCE,
            )
        )
    unique = {(c.field, c.value): c for c in reversed(candidates)}
    return sorted(unique.values(), key=lambda candidate: candidate.start)


@dataclass(frozen=True, slots=True)
class Identifiers:
    """Identifiers of a message used to find its shipment and to learn new aliases."""

    bookings: tuple[str, ...]
    previous_bookings: tuple[str, ...]
    containers: tuple[str, ...]
    operations: tuple[str, ...] = ()
    bills_of_lading: tuple[str, ...] = ()

    def merged(self, other: Identifiers) -> Identifiers:
        """Union of two sets of identifiers, keeping the order of first appearance."""
        return Identifiers(
            bookings=_union(self.bookings, other.bookings),
            previous_bookings=_union(self.previous_bookings, other.previous_bookings),
            containers=_union(self.containers, other.containers),
            operations=_union(self.operations, other.operations),
            bills_of_lading=_union(self.bills_of_lading, other.bills_of_lading),
        )

    @property
    def is_empty(self) -> bool:
        """True if there is no identifier of any kind."""
        return not (
            self.bookings
            or self.previous_bookings
            or self.containers
            or self.operations
            or self.bills_of_lading
        )


def _union(first: tuple[str, ...], second: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*first, *second)))


def find_identifiers(text: str) -> Identifiers:
    """Collect the bookings and valid containers of a message.

    Args:
        text: Text of the message, subject included.

    Returns:
        Current and replaced bookings (A-20) and containers with a valid check digit.
    """
    bookings = find_bookings(text)
    return Identifiers(
        bookings=tuple(dict.fromkeys(b.value for b in bookings if b.qualifier is None)),
        previous_bookings=tuple(
            dict.fromkeys(b.value for b in bookings if b.qualifier == "previous")
        ),
        containers=tuple(dict.fromkeys(c.value for c in find_containers(text) if c.valid)),
        operations=tuple(dict.fromkeys(o.value for o in find_operations(text) if o.valid)),
        bills_of_lading=tuple(dict.fromkeys(b.value for b in find_bills_of_lading(text))),
    )
