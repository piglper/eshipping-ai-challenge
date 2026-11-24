"""Discrepancy policy, part 1: source authority and current value of a field (ADR-0009 §1-§3).

Everything here is a pure function of the observations and the configuration, so that the
same inputs always give the same current value and a past state can be recomputed (RF-61).
"""

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Literal

from pydantic import NonNegativeInt, PositiveInt

from eshipping_ai.domain.model import Confidence, DomainModel, FieldState, Observation
from eshipping_ai.domain.vocabulary import (
    EventClassifier,
    ObservationStatus,
    SourceRank,
    SourceRole,
    Zone,
)

RELIABLE_RANKS = frozenset({SourceRank.A, SourceRank.B})
"""Ranks whose values can become the current value (ADR-0009 §3, rule 3)."""


class FieldRule(DomainModel):
    """How one field is read, compared with the ERP and prioritised."""

    kind: Literal["date", "text", "count", "reference"] = "text"
    critical: bool = False
    authority: dict[SourceRank, tuple[SourceRole, ...]]
    erp_key: str | None = None
    erp_actual_key: str | None = None
    min_confidence: Confidence = 0.9


class ReconciliationConfig(DomainModel):
    """Versioned configuration of the discrepancy policy (``config/reconciliation.yaml``)."""

    version: str
    conflict_window_hours: PositiveInt = 24
    erp_stale_after_hours: PositiveInt = 24
    urgent_horizon_hours: PositiveInt = 72
    approx_days: NonNegativeInt = 2
    vessel_similarity: Confidence = 0.92
    fields: dict[str, FieldRule]


def rank_for(config: ReconciliationConfig, field: str, role: SourceRole) -> SourceRank:
    """Authority of a source role for a field.

    Args:
        config: Policy configuration.
        field: Field key.
        role: Role of the original author of the message.

    Returns:
        The rank; a role the field does not list is informative (C), and a human review
        always has authority.
    """
    if role is SourceRole.HUMAN_REVIEW:
        return SourceRank.A
    rule = config.fields.get(field)
    if rule is not None:
        for rank in (SourceRank.A, SourceRank.B):
            if role in rule.authority.get(rank, ()):
                return rank
    return SourceRank.C


def _state(  # noqa: PLR0913, PLR0917 - one value per attribute of the projection
    shipment_id: str,
    field: str,
    winner: Observation | None,
    rule: str,
    computed_at: datetime,
    config: ReconciliationConfig,
    *,
    conflict: bool = False,
    pending: Iterable[Observation] = (),
) -> FieldState:
    return FieldState(
        shipment_id=shipment_id,
        field=field,
        value=winner.value if winner else None,
        winning_observation_id=winner.observation_id if winner else None,
        rule=rule,
        in_conflict=conflict,
        pending_confirmation=tuple(o.observation_id for o in pending),
        computed_at=computed_at,
        config_version=config.version,
    )


def _near_conflict(
    pool: list[Observation], top: Observation, window: timedelta
) -> list[Observation]:
    """Reliable sources that disagree with the freshest one almost at the same time."""
    return [
        other
        for other in pool
        if other.value != top.value
        and top.known_at - other.known_at < window
        and SourceRank.A in {top.source_rank, other.source_rank}
    ]


def project_field(
    shipment_id: str,
    field: str,
    observations: Iterable[Observation],
    config: ReconciliationConfig,
    computed_at: datetime,
) -> FieldState:
    """Compute the current value of a field from the mails (ADR-0009 §3).

    Rules, in order: a human review wins (6); an actual value beats any estimate (2); among
    reliable sources the freshest wins (3); an informative source never replaces, it waits
    for confirmation (4); sources of authority that disagree within the conflict window, or
    two different actual values, make a conflict (5, 2).

    Args:
        shipment_id: Shipment being projected.
        field: Field key.
        observations: Observations of the shipment; others are ignored.
        config: Policy configuration.
        computed_at: Time of the computation.

    Returns:
        The projection. A field in conflict has no value until a person resolves it.
    """
    candidates = [
        o
        for o in observations
        if o.shipment_id == shipment_id
        and o.field == field
        and o.status is ObservationStatus.ACTIVE
        and o.zone is not Zone.NOT_PROPOSED
    ]
    humans = [o for o in candidates if o.source_role is SourceRole.HUMAN_REVIEW]
    reliable = [o for o in candidates if o.source_rank in RELIABLE_RANKS and o not in humans]
    informative = [o for o in candidates if o.source_rank is SourceRank.C]

    def build(
        winner: Observation | None,
        rule: str,
        *,
        conflict: bool = False,
        pending: Iterable[Observation] = (),
    ) -> FieldState:
        return _state(
            shipment_id,
            field,
            winner,
            rule,
            computed_at,
            config,
            conflict=conflict,
            pending=pending,
        )

    if humans:
        winner = max(humans, key=lambda o: o.known_at)
        contradicting = [
            o
            for o in reliable
            if o.source_rank is SourceRank.A
            and o.known_at > winner.known_at
            and o.value != winner.value
        ]
        return build(winner, "human_review", pending=contradicting)
    if not reliable:
        return build(
            None, "only_informative" if informative else "no_observations", pending=informative
        )
    actual = [o for o in reliable if o.classifier is EventClassifier.ACTUAL]
    pool = actual or reliable
    if len({o.value for o in actual}) > 1:
        return build(None, "conflicting_actuals", conflict=True, pending=pool)
    top = max(pool, key=lambda o: o.known_at)
    window = timedelta(hours=config.conflict_window_hours)
    clashing = _near_conflict(pool, top, window)
    if clashing:
        return build(None, "near_simultaneous", conflict=True, pending=[top, *clashing])
    newer_informative = [
        o for o in informative if o.value != top.value and o.known_at > top.known_at
    ]
    rule = "actual_over_estimate" if actual else "freshest_reliable"
    return build(top, rule, pending=newer_informative)
