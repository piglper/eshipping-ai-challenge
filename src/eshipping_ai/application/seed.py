"""Use case: start the association index from the ERP (RF-40).

The ERP is the list of shipments EShipping handles. Each row becomes a shipment, identified
by its operation number, known under that number and under its booking. Everything else
(replaced bookings, containers) is learned from the mails.
"""

from collections.abc import Sequence
from datetime import datetime

from eshipping_ai.domain.model import ErpRecord, ShipmentAlias
from eshipping_ai.domain.ports import AliasStore
from eshipping_ai.domain.vocabulary import AliasType


def seed_aliases(
    records: Sequence[ErpRecord], aliases: AliasStore, read_at: datetime
) -> dict[str, str]:
    """Register the operation and the booking of every ERP row as aliases.

    Args:
        records: Rows of an ERP read.
        aliases: The association index.
        read_at: When the ERP was read; the aliases are valid from then.

    Returns:
        Shipment identifier to ERP operation number, ready for the reconciliation. In the
        PoC the identifier of a shipment is its operation number.
    """
    shipments: dict[str, str] = {}
    for record in records:
        shipments[record.operation] = record.operation
        values = {
            AliasType.OPERATION: record.operation,
            AliasType.BOOKING: record.normalized.get("booking"),
        }
        for alias_type, value in values.items():
            if value:
                aliases.add_alias(
                    ShipmentAlias(
                        shipment_id=record.operation,
                        alias_type=alias_type,
                        value=value,
                        valid_from=read_at,
                    )
                )
    return shipments
