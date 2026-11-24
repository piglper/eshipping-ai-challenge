"""Use case: reconcile shipments with the ERP (RF-51 to RF-56).

For every shipment the current value of each configured field is projected from the
observations (ADR-0009 §3), compared with the latest ERP read and turned into a verdict
with a priority. Urgent verdicts are notified grouped by shipment. Nothing is written to
the ERP: the verdicts are proposals for an operator (RF-55).
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from eshipping_ai.domain.comparison import ComparisonInput, compare_field, erp_quality_issues
from eshipping_ai.domain.model import ErpRecord, FieldState, Observation, Verdict
from eshipping_ai.domain.policy import ReconciliationConfig, project_field
from eshipping_ai.domain.ports import (
    Clock,
    ERPGateway,
    ErpStore,
    Notifier,
    ObservationStore,
    ProjectionStore,
)
from eshipping_ai.domain.vocabulary import ObservationStatus, Priority

_ALIAS_FIELDS = ("booking",)


@dataclass(slots=True)
class ReconcileReport:
    """What a reconciliation run did; counts only, never content."""

    shipments: int = 0
    not_in_erp: int = 0
    verdicts: Counter[str] = field(default_factory=Counter)
    conflicts: int = 0
    urgent: int = 0
    quality_issues: int = 0


class ReconcileShipments:
    """Projects, compares and prioritises every shipment against one ERP read."""

    def __init__(  # noqa: PLR0913, PLR0917 - one collaborator per port
        self,
        erp: ERPGateway,
        erp_store: ErpStore,
        observations: ObservationStore,
        projections: ProjectionStore,
        notifier: Notifier,
        clock: Clock,
        config: ReconciliationConfig,
    ) -> None:
        """Create the use case.

        Args:
            erp: Read-only access to the ERP.
            erp_store: Where ERP reads are kept.
            observations: Where the observations of the shipments are read from.
            projections: Where field states and verdicts are stored.
            notifier: Receives the urgent verdicts of each shipment.
            clock: Current time.
            config: Discrepancy policy.
        """
        self._erp = erp
        self._erp_store = erp_store
        self._observations = observations
        self._projections = projections
        self._notifier = notifier
        self._clock = clock
        self._config = config

    def run(self, shipments: Mapping[str, str]) -> ReconcileReport:
        """Reconcile shipments with the ERP.

        Args:
            shipments: Shipment identifier to ERP operation number.

        Returns:
            Counts of what was found.
        """
        snapshot, records = self._erp.read()
        self._erp_store.add_erp_snapshot(snapshot, records)
        by_operation = {record.operation: record for record in records}
        report = ReconcileReport()
        for shipment_id, operation in shipments.items():
            report.shipments += 1
            record = by_operation.get(operation)
            if record is None:
                report.not_in_erp += 1
                continue
            observations = self._observations.observations_for(shipment_id)
            verdicts = self._reconcile(shipment_id, observations, record, snapshot.read_at, report)
            self._projections.save_verdicts(verdicts)
            urgent = [v for v in verdicts if v.priority is Priority.P1]
            if urgent:
                report.urgent += len(urgent)
                self._notifier.notify(shipment_id, urgent)
        return report

    def _reconcile(
        self,
        shipment_id: str,
        observations: Sequence[Observation],
        record: ErpRecord,
        read_at: datetime,
        report: ReconcileReport,
    ) -> list[Verdict]:
        now = self._clock.now()
        issues = erp_quality_issues(record)
        report.quality_issues += len(issues)
        active = [o for o in observations if o.status is ObservationStatus.ACTIVE]
        last_known = max((o.known_at for o in active), default=None)
        states: list[FieldState] = []
        verdicts: list[Verdict] = []
        for name, rule in self._config.fields.items():
            state = project_field(shipment_id, name, observations, self._config, now)
            states.append(state)
            report.conflicts += state.in_conflict
            winner = next(
                (o for o in active if o.observation_id == state.winning_observation_id), None
            )
            history = {
                o.value
                for o in active
                if name in _ALIAS_FIELDS and o.field == name and o is not winner
            }
            verdict = compare_field(
                ComparisonInput(
                    shipment_id=shipment_id,
                    field=name,
                    rule=rule,
                    config=self._config,
                    state=state,
                    winner=winner,
                    history=history,
                    erp=record,
                    erp_read_at=read_at,
                    last_mail_known_at=last_known,
                    issues=issues,
                    now=now,
                )
            )
            if verdict is not None:
                verdicts.append(verdict)
                report.verdicts[verdict.code.value] += 1
        self._projections.save_field_states(states)
        return verdicts
