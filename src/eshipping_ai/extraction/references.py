"""Deterministic extraction of shipping identifiers (RF-20 to RF-23, RF-40).

Each mention carries its position in the text so that it can be quoted as evidence. Numbers
that look like identifiers but have no context are not extracted (A-18): a booking needs a
keyword next to it. Containers are the exception because their check digit (ISO 6346) makes
a false positive very unlikely; a container-like code with a wrong check digit is reported
as invalid instead of being dropped, because it is usually a typing or OCR error worth a
review.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from eshipping_ai.domain.identifiers import is_valid_container_number, normalize_reference


class ReferenceKind(StrEnum):
    """Kind of identifier found in a text."""

    CONTAINER = "container"
    BOOKING = "booking"
    OPERATION = "operation"
    OPERATION_PREFIX = "operation_prefix"
    BILL_OF_LADING = "bl"


@dataclass(frozen=True, slots=True)
class ReferenceMention:
    """An identifier found in a text.

    ``valid`` is False only for container-like codes whose check digit is wrong, and for
    truncated operation numbers. ``qualifier`` is ``"previous"`` for a booking that the
    text says has been replaced (A-20).
    """

    kind: ReferenceKind
    value: str
    raw: str
    start: int
    end: int
    valid: bool = True
    qualifier: str | None = None


_BOOKING_VALUE = r"(?P<v>(?:[A-Z]{3,4}\d{7,8}|\d{8,9}))(?![A-Za-z0-9])"
_BOOKING_FILLER = (
    r"(?:\s+(?:confirmation|amendment|request|advice|notice|number|no|ref|reference|"
    r"nº|n°|num|número))*"
)
_BOOKING_RE = re.compile(
    rf"(?<![A-Za-z])(?:booking|bkg|reserva){_BOOKING_FILLER}\.?\s*[:=#]?\s*{_BOOKING_VALUE}",
    re.IGNORECASE,
)
# Only the label: "Booking confirmation 990000101" also says what the message is about.
_BOOKING_LABEL_RE = re.compile(
    r"(?<![A-Za-z])(?:booking|bkg|reserva)(?:\s+(?:number|no|ref|reference|nº|n°|num|número))*"
    rf"\.?\s*[:=#]?\s*{_BOOKING_VALUE}",
    re.IGNORECASE,
)
_PREVIOUS_BOOKING_RE = re.compile(
    rf"(?:replaces|replacing|supersedes|sustituye(?: a)?(?: al)?|reemplaza(?: a)?(?: al)?)"
    rf"\s+(?:booking\s+)?{_BOOKING_VALUE}",
    re.IGNORECASE,
)
_OPERATION_RE = re.compile(r"(?<![A-Za-z0-9])ES\d{8}(?!\d)")
_OPERATION_PREFIX_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:exp(?:ediente)?\.?\s*:?\s*)(?P<v>ES\d{3,7})(?!\d)", re.IGNORECASE
)
_BL_RE = re.compile(
    r"(?<![A-Za-z])(?:b/?l|b\.l\.|bill of lading|mbl|hbl|swb|master)\b"
    r"(?:\s+(?:number|no|nº|n°|#))?\s*[:=#]?\s*"
    r"(?P<v>(?=[A-Z0-9]*\d)[A-Z]{3,5}[A-Z0-9]{6,12})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_CONTAINER_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<owner>[A-Z]{3}[UJZR])[ \-]?(?P<serial>\d{6})[ \-]?(?P<check>\d)"
    r"(?![A-Za-z0-9])"
)
_SEAL_CONTEXT_RE = re.compile(r"(?:seal|precinto|sello)s?\s*(?:n[oº°.]*)?\s*[:=#]?\s*$", re.I)
_SEAL_LOOKBACK = 24


def find_containers(text: str) -> list[ReferenceMention]:
    """Find ISO 6346 container numbers, skipping seals that look like containers.

    Args:
        text: Text to search.

    Returns:
        One mention per number, valid or not, in order of appearance.
    """
    found: list[ReferenceMention] = []
    for match in _CONTAINER_RE.finditer(text):
        before = text[max(0, match.start() - _SEAL_LOOKBACK) : match.start()]
        if _SEAL_CONTEXT_RE.search(before):
            continue
        number = "".join(match.group("owner", "serial", "check"))
        found.append(
            ReferenceMention(
                ReferenceKind.CONTAINER,
                number,
                match.group(0),
                match.start(),
                match.end(),
                valid=is_valid_container_number(number),
            )
        )
    return found


def strip_booking_labels(text: str) -> str:
    """Drop the word that labels a booking number, keeping the number.

    In ``RE: BKG 990000101`` the word is the name of an identifier, not the topic of the
    message: a whole thread keeps it in the subject, whatever each reply is about.

    Args:
        text: Text to clean.

    Returns:
        The text with every ``booking <number>`` reduced to the number; ``booking
        confirmation <number>`` is kept, because it does say what the message is about.
    """
    return _BOOKING_LABEL_RE.sub(lambda match: match.group("v"), text)


def find_bookings(text: str) -> list[ReferenceMention]:
    """Find booking numbers next to a keyword; a replaced booking is marked as previous.

    Args:
        text: Text to search.

    Returns:
        The mentions in order of appearance, without repeats of the same span.
    """
    found: dict[tuple[int, int], ReferenceMention] = {}
    for pattern, qualifier in ((_BOOKING_RE, None), (_PREVIOUS_BOOKING_RE, "previous")):
        for match in pattern.finditer(text):
            span = match.span("v")
            found.setdefault(
                span,
                ReferenceMention(
                    ReferenceKind.BOOKING,
                    normalize_reference(match["v"]),
                    match["v"],
                    *span,
                    qualifier=qualifier,
                ),
            )
    return sorted(found.values(), key=lambda mention: mention.start)


def find_operations(text: str) -> list[ReferenceMention]:
    """Find shipment numbers (``ES`` and eight digits) and truncated ones (A-17).

    Args:
        text: Text to search.

    Returns:
        Complete numbers as valid mentions and truncated ones as invalid prefixes.
    """
    found = [
        ReferenceMention(ReferenceKind.OPERATION, m.group(0), m.group(0), m.start(), m.end())
        for m in _OPERATION_RE.finditer(text)
    ]
    found += [
        ReferenceMention(
            ReferenceKind.OPERATION_PREFIX, m["v"].upper(), m["v"], *m.span("v"), valid=False
        )
        for m in _OPERATION_PREFIX_RE.finditer(text)
    ]
    return sorted(found, key=lambda mention: mention.start)


def find_bills_of_lading(text: str) -> list[ReferenceMention]:
    """Find bill of lading numbers next to a keyword (``B/L``, ``MBL``, ``SWB``...).

    Args:
        text: Text to search.

    Returns:
        The mentions in order of appearance.
    """
    return [
        ReferenceMention(
            ReferenceKind.BILL_OF_LADING,
            normalize_reference(m["v"]),
            m["v"],
            *m.span("v"),
        )
        for m in _BL_RE.finditer(text)
    ]


def find_references(text: str) -> list[ReferenceMention]:
    """Find every kind of identifier in a text.

    Args:
        text: Text to search.

    Returns:
        All mentions in order of appearance.
    """
    mentions = [
        *find_operations(text),
        *find_bookings(text),
        *find_bills_of_lading(text),
        *find_containers(text),
    ]
    return sorted(mentions, key=lambda mention: (mention.start, mention.kind))
