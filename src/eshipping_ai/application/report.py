"""Use case: the view of a shipment for an operator (RF-80, RF-81).

For each field: the current value according to the mails, the rule that chose it, the
literal quote that supports it, and the verdict against the ERP with its priority. The
lines are sorted with what needs attention first.
"""

from dataclasses import dataclass
from datetime import datetime

from eshipping_ai.domain.ports import ObservationStore, ProjectionStore
from eshipping_ai.domain.vocabulary import Priority

_PRIORITY_ORDER = {Priority.P1: 0, Priority.P2: 1, Priority.P3: 2, None: 3}


@dataclass(frozen=True, slots=True)
class FieldLine:
    """One field of a shipment as an operator sees it."""

    field: str
    mail_value: str | None
    erp_value: str | None
    verdict: str | None
    priority: str | None
    rule: str
    in_conflict: bool
    evidence: str | None
    source_role: str | None
    known_at: datetime | None


@dataclass(frozen=True, slots=True)
class ShipmentReport:
    """Every field of a shipment, most urgent first."""

    shipment_id: str
    lines: tuple[FieldLine, ...]


def shipment_report(
    shipment_id: str, projections: ProjectionStore, observations: ObservationStore
) -> ShipmentReport:
    """Build the view of one shipment.

    Args:
        shipment_id: The shipment.
        projections: Where field states and verdicts are read from.
        observations: Where the winning observations are read from, for their quotes.

    Returns:
        One line per projected field.
    """
    by_id = {o.observation_id: o for o in observations.observations_for(shipment_id)}
    verdicts = {v.field: v for v in projections.verdicts_for(shipment_id)}
    lines = []
    for state in projections.field_states_for(shipment_id):
        verdict = verdicts.get(state.field)
        winner = by_id.get(state.winning_observation_id or "")
        lines.append(
            FieldLine(
                field=state.field,
                mail_value=state.value,
                erp_value=verdict.erp_value if verdict else None,
                verdict=verdict.code.value if verdict else None,
                priority=verdict.priority.value if verdict and verdict.priority else None,
                rule=verdict.rule if verdict else state.rule,
                in_conflict=state.in_conflict,
                evidence=winner.evidence.text if winner else None,
                source_role=winner.source_role.value if winner else None,
                known_at=winner.known_at if winner else None,
            )
        )
    lines.sort(
        key=lambda line: (
            _PRIORITY_ORDER[Priority(line.priority) if line.priority else None],
            line.field,
        )
    )
    return ShipmentReport(shipment_id, tuple(lines))
