"""Association of a thread with its shipments (RF-40 to RF-44).

The identifiers of the whole thread are looked up in the alias index, from the strongest to
the weakest: shipment number, booking (current or replaced, A-20), bill of lading and
container. The first kind that finds something decides, because a container is reused over
time and must not override a booking. An identifier known to several shipments is not
resolved by guessing: those associations go to review (A-19). When one shipment is found
without doubt, the bookings and containers the thread mentions that the index did not know
become new aliases, which is how a rollover with a new booking keeps its thread together.
"""

from dataclasses import dataclass
from datetime import datetime

from eshipping_ai.domain.model import ShipmentAlias
from eshipping_ai.domain.ports import AliasStore
from eshipping_ai.domain.vocabulary import AliasType, AssociationMethod, AssociationStatus
from eshipping_ai.extraction.events import Identifiers

_AMBIGUOUS_CONFIDENCE = 0.5
_LEVELS: tuple[tuple[AliasType, AssociationMethod, float], ...] = (
    (AliasType.OPERATION, AssociationMethod.OPERATION, 0.99),
    (AliasType.BOOKING, AssociationMethod.BOOKING, 0.98),
    (AliasType.BILL_OF_LADING, AssociationMethod.BILL_OF_LADING, 0.95),
    (AliasType.CONTAINER, AssociationMethod.CONTAINER, 0.85),
)


@dataclass(frozen=True, slots=True)
class Match:
    """A shipment found for a thread, how and how sure."""

    shipment_id: str
    method: AssociationMethod
    matched_value: str
    confidence: float
    status: AssociationStatus


def _values(identifiers: Identifiers, alias_type: AliasType) -> tuple[str, ...]:
    return {
        AliasType.OPERATION: identifiers.operations,
        AliasType.BOOKING: (*identifiers.bookings, *identifiers.previous_bookings),
        AliasType.BILL_OF_LADING: identifiers.bills_of_lading,
        AliasType.CONTAINER: identifiers.containers,
    }.get(alias_type, ())


def find_shipments(identifiers: Identifiers, aliases: AliasStore) -> list[Match]:
    """Find the shipments a thread talks about.

    Args:
        identifiers: Identifiers found in the whole thread.
        aliases: The association index.

    Returns:
        The matches of the strongest kind of identifier that finds any, one per shipment;
        empty if the index knows none of the identifiers.
    """
    for alias_type, method, confidence in _LEVELS:
        found: dict[str, Match] = {}
        for value in _values(identifiers, alias_type):
            known = {alias.shipment_id for alias in aliases.find_aliases(alias_type, value)}
            for shipment_id in sorted(known):
                ambiguous = len(known) > 1
                match = Match(
                    shipment_id=shipment_id,
                    method=method,
                    matched_value=value,
                    confidence=_AMBIGUOUS_CONFIDENCE if ambiguous else confidence,
                    status=AssociationStatus.IN_REVIEW if ambiguous else AssociationStatus.AUTO,
                )
                found.setdefault(shipment_id, match)
        if found:
            return list(found.values())
    return []


def learn_aliases(
    matches: list[Match], identifiers: Identifiers, aliases: AliasStore, at: datetime
) -> int:
    """Register the bookings and containers of a thread that belongs to one shipment.

    Args:
        matches: What :func:`find_shipments` found.
        identifiers: Identifiers found in the whole thread.
        aliases: The association index, where the new aliases are added.
        at: Moment from which the aliases are valid (the date of the message).

    Returns:
        How many aliases were new. Nothing is learned from a weak (container) match or from
        a thread with several candidate shipments: it would spread a mistake.
    """
    strong = (
        AssociationMethod.OPERATION,
        AssociationMethod.BOOKING,
        AssociationMethod.BILL_OF_LADING,
    )
    if len(matches) != 1 or matches[0].status is not AssociationStatus.AUTO:
        return 0
    if matches[0].method not in strong:
        return 0
    shipment_id = matches[0].shipment_id
    learned = 0
    for alias_type, values in (
        (AliasType.BOOKING, identifiers.bookings),
        (AliasType.CONTAINER, identifiers.containers),
    ):
        for value in values:
            if aliases.find_aliases(alias_type, value):
                continue
            aliases.add_alias(
                ShipmentAlias(
                    shipment_id=shipment_id, alias_type=alias_type, value=value, valid_from=at
                )
            )
            learned += 1
    return learned
