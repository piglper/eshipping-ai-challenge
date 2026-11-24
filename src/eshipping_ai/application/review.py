"""Use case: an operator's decision on a field (RF-70 to RF-72).

A decision never edits what a source said. Accepting or correcting a value adds a human
observation, which has the highest authority (ADR-0009 §3); rejecting one marks the
observation that supported it as superseded, so the next one takes its place. Both keep
the history and are the signal the system learns from (docs/08_aprendizaje_continuo.md).
After a decision the shipment is projected and compared with the ERP again.

A human observation has no mail behind it: its source is the correction itself
(``correction:<id>``) and its evidence is the operator's reason.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, tzinfo

from eshipping_ai.domain.model import Correction, Evidence, Observation, Provenance
from eshipping_ai.domain.policy import ReconciliationConfig
from eshipping_ai.domain.ports import Clock, ObservationStore, ProjectionStore
from eshipping_ai.domain.vocabulary import (
    CorrectionAction,
    EventClassifier,
    EventType,
    ExtractionTier,
    SourceRank,
    SourceRole,
    TimePrecision,
    Zone,
)

HUMAN_VERSION = "human-1"
_EVENT_OF_FIELD: dict[str, EventType] = {
    "booking": EventType.BOOKING_CONFIRMED,
    "vessel": EventType.DEPARTURE,
    "vessel_departure": EventType.DEPARTURE,
    "vessel_arrival_pod": EventType.ARRIVAL,
    "stuffing": EventType.STUFFING,
    "customs_release": EventType.CUSTOMS_RELEASED,
    "equipment_count": EventType.BOOKING_CONFIRMED,
    "cutoff_document": EventType.DOCUMENT_CUTOFF,
    "cutoff_vgm": EventType.VGM_CUTOFF,
    "cutoff_full": EventType.FULL_CONTAINER_CUTOFF,
    "containers": EventType.STUFFING,
    "bill_of_lading": EventType.BL_ISSUED,
}


class ReviewError(ValueError):
    """A decision that cannot be applied as asked."""


@dataclass(frozen=True, slots=True)
class Decision:
    """What an operator decided on one field of one shipment."""

    shipment_id: str
    field: str
    action: CorrectionAction
    user_id: str
    value: str | None = None
    reason: str | None = None
    classifier: EventClassifier = EventClassifier.ESTIMATED


class ApplyCorrection:
    """Records an operator's decision as observations, never as an edit."""

    def __init__(
        self,
        observations: ObservationStore,
        projections: ProjectionStore,
        clock: Clock,
        config: ReconciliationConfig,
        local_tz: tzinfo,
    ) -> None:
        """Create the use case.

        Args:
            observations: Where observations are added or superseded.
            projections: Where the current value of the field is read.
            clock: Current time.
            config: Discrepancy policy, for the kind of each field.
            local_tz: Time zone of a corrected date.
        """
        self._observations = observations
        self._projections = projections
        self._clock = clock
        self._config = config
        self._tz = local_tz

    def apply(self, decision: Decision) -> Correction:
        """Apply a decision.

        Args:
            decision: Field, action and, for a correction, the new value.

        Returns:
            The correction, as the record of the decision.

        Raises:
            ReviewError: If the field is unknown, there is nothing to accept or reject, or
                the new value does not fit the field.
        """
        if decision.field not in self._config.fields:
            msg = f"unknown field: {decision.field}"
            raise ReviewError(msg)
        if decision.action is CorrectionAction.REJECT and not decision.reason:
            msg = "a rejection records its reason"
            raise ReviewError(msg)
        if decision.action is CorrectionAction.CORRECT and not decision.value:
            msg = "a correction needs the new value"
            raise ReviewError(msg)
        now = self._clock.now()
        state = next(
            (
                s
                for s in self._projections.field_states_for(decision.shipment_id)
                if s.field == decision.field
            ),
            None,
        )
        winner_id = state.winning_observation_id if state else None
        new_value = decision.value if decision.action is CorrectionAction.CORRECT else None
        key = "\x1f".join(
            (decision.shipment_id, decision.field, decision.action, str(new_value), now.isoformat())
        )
        correction = Correction(
            correction_id=f"cor-{hashlib.sha256(key.encode()).hexdigest()[:16]}",
            task_id=f"field:{decision.shipment_id}:{decision.field}",
            user_id=decision.user_id,
            action=decision.action,
            new_value=new_value,
            reason=decision.reason,
            created_at=now,
        )
        if decision.action is CorrectionAction.REJECT:
            if winner_id is None:
                msg = "there is no value to reject"
                raise ReviewError(msg)
            self._observations.mark_superseded(winner_id, correction.correction_id, now)
            return correction
        value = (
            new_value
            if decision.action is CorrectionAction.CORRECT
            else (state.value if state else None)
        )
        if value is None:
            msg = "there is no value to accept"
            raise ReviewError(msg)
        self._observations.add_observations([self._observation(decision, correction, value)])
        return correction

    def _observation(self, decision: Decision, correction: Correction, value: str) -> Observation:
        kind = self._config.fields[decision.field].kind
        event_time = None
        if kind == "date":
            try:
                event_time = datetime.combine(date.fromisoformat(value), time(0), tzinfo=self._tz)
            except ValueError as error:
                msg = f"a date is written as YYYY-MM-DD: {value!r}"
                raise ReviewError(msg) from error
        elif kind == "count" and not value.isdigit():
            msg = f"a count is a whole number: {value!r}"
            raise ReviewError(msg)
        reason = decision.reason or f"{decision.action.value} by {decision.user_id}"
        return Observation(
            observation_id=f"obs-{correction.correction_id}",
            shipment_id=decision.shipment_id,
            message_id=f"correction:{correction.correction_id}",
            event_type=_EVENT_OF_FIELD.get(decision.field, EventType.BOOKING_AMENDED),
            classifier=decision.classifier if kind == "date" else EventClassifier.ESTIMATED,
            field=decision.field,
            value=value.upper() if decision.field == "vessel" else value,
            value_raw=value,
            event_time=event_time,
            time_precision=TimePrecision.DATE if event_time else None,
            vessel=value.upper() if decision.field == "vessel" else None,
            source_role=SourceRole.HUMAN_REVIEW,
            source_rank=SourceRank.A,
            evidence=Evidence(text=reason[:500], start=0, end=len(reason[:500])),
            known_at=correction.created_at,
            recorded_at=correction.created_at,
            provenance=Provenance(
                tier=ExtractionTier.HUMAN,
                extractor_version=HUMAN_VERSION,
                config_version=self._config.version,
            ),
            confidence=1.0,
            zone=Zone.AUTO,
        )
