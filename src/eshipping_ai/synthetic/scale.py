"""Replicate a specification into a large synthetic data set for the volume test (F4.5).

Each copy of a shipment is a different shipment: its operation number, its bookings and its
containers (with a valid ISO 6346 check digit) are renumbered, so that association has to
find it by its own identifiers. Every mail of a copy after the first ends with a sign-off
line of its own, made of letters only (``Equipo BCD``), so that a mail with no identifier
(``Gracias``) is a new message and not a duplicate of the same mail in the first copy:
ingestion tells messages apart by their text and the minute they were sent.
"""

import json
import re

from eshipping_ai.domain.identifiers import iso6346_check_digit
from eshipping_ai.synthetic.spec import Spec, SpecMail, SpecShipment

_BOOKING_RE = re.compile(r"\b990000(\d{3})\b")
_CONTAINER_RE = re.compile(r"\b(SYNU)\d(\d{4})(\d)\d\b")
_MAX_SHIPMENTS = 99_999


def _renumber(text: str, original: str, operation: str, number: int) -> str:
    text = text.replace(original, operation)
    text = _BOOKING_RE.sub(lambda m: f"9{number:05d}{m[1]}", text)

    def container(match: re.Match[str]) -> str:
        prefix = f"{match[1]}{number:05d}{match[3]}"
        return f"{prefix}{iso6346_check_digit(prefix)}"

    return _CONTAINER_RE.sub(container, text)


def _tag(copy: int) -> str:
    """Letters that name a copy: ``A``, ``B``... ``Z``, ``BA``... (no digits to extract)."""
    letters = ""
    while True:
        copy, rest = divmod(copy, 26)
        letters = chr(ord("A") + rest) + letters
        if copy == 0:
            return letters


def _sign(mail: SpecMail, copy: int) -> SpecMail:
    if copy == 0:
        return mail
    return mail.model_copy(update={"body": f"{mail.body.rstrip()}\n\nEquipo {_tag(copy)}\n"})


def _copy_shipment(shipment: SpecShipment, number: int, copy: int) -> SpecShipment:
    operation = f"ES26{number:06d}"
    dumped = json.dumps(shipment.model_dump(mode="json", by_alias=True), ensure_ascii=False)
    renamed = SpecShipment.model_validate(
        json.loads(_renumber(dumped, shipment.operation, operation, number))
    )
    return renamed.model_copy(update={"mails": tuple(_sign(m, copy) for m in renamed.mails)})


def replicate(spec: Spec, copies: int) -> Spec:
    """Build a specification with ``copies`` renumbered copies of every shipment.

    Args:
        spec: The base specification; its bookings and containers follow the synthetic
            patterns ``990000nnn`` and ``SYNU``.
        copies: How many times to repeat every shipment and noise mail.

    Returns:
        The larger specification, valid like the base one.

    Raises:
        ValueError: If ``copies`` is not positive or the shipments would not fit in the
            numbering.
    """
    if copies < 1 or copies * len(spec.shipments) > _MAX_SHIPMENTS:
        msg = f"copies must be between 1 and {_MAX_SHIPMENTS // len(spec.shipments)}"
        raise ValueError(msg)
    shipments = [
        _copy_shipment(shipment, copy * len(spec.shipments) + index + 1, copy)
        for copy in range(copies)
        for index, shipment in enumerate(spec.shipments)
    ]
    noise = [
        _sign(mail, copy).model_copy(update={"id": f"N{copy * len(spec.noise) + index + 1}"})
        for copy in range(copies)
        for index, mail in enumerate(spec.noise)
    ]
    return spec.model_copy(update={"shipments": tuple(shipments), "noise": tuple(noise)})
