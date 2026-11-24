from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from eshipping_ai.domain.model import (
    Correction,
    Evidence,
    FieldState,
    Observation,
    Provenance,
)
from eshipping_ai.domain.vocabulary import (
    CorrectionAction,
    EventClassifier,
    EventType,
    ExtractionTier,
    ObservationStatus,
    SourceRank,
    SourceRole,
    TimePrecision,
    Zone,
)

T0 = datetime(2026, 9, 10, 9, 30, tzinfo=UTC)


def observation(**overrides: Any) -> Observation:
    """Valid synthetic observation: a carrier announcing an estimated departure."""
    data: dict[str, Any] = {
        "observation_id": "obs-1",
        "shipment_id": "shp-1",
        "message_id": "msg-1",
        "event_type": EventType.DEPARTURE,
        "classifier": EventClassifier.ESTIMATED,
        "field": "vessel_departure.time",
        "value": "2026-09-22",
        "value_raw": "ETD 22/09",
        "event_time": datetime(2026, 9, 22, tzinfo=UTC),
        "time_precision": TimePrecision.DATE,
        "location_unlocode": "ESVLC",
        "vessel": "SYNTHETIC STAR",
        "equipment": ("csqu3054383",),
        "source_role": SourceRole.CARRIER,
        "source_rank": SourceRank.A,
        "evidence": Evidence(text="ETD 22/09", start=120, end=129),
        "known_at": T0,
        "recorded_at": T0 + timedelta(minutes=2),
        "provenance": Provenance(
            tier=ExtractionTier.RULE, extractor_version="1", config_version="c1"
        ),
        "confidence": 0.97,
        "zone": Zone.AUTO,
    }
    data.update(overrides)
    return Observation(**data)


def test_valid_observation_is_normalised_and_frozen() -> None:
    obs = observation()
    assert obs.equipment == ("CSQU3054383",)
    with pytest.raises(ValidationError):
        obs.value = "2026-09-23"  # type: ignore[misc]


def test_idempotency_key_depends_on_source_field_value_and_version() -> None:
    base = observation()
    assert base.idempotency_key == observation(observation_id="obs-2").idempotency_key
    assert base.idempotency_key != observation(value="2026-09-23").idempotency_key
    newer = Provenance(tier=ExtractionTier.RULE, extractor_version="2", config_version="c1")
    assert base.idempotency_key != observation(provenance=newer).idempotency_key


@pytest.mark.parametrize(
    "overrides",
    [
        {"message_id": None},
        {"document_id": "doc-1"},
        {"time_precision": None},
        {"event_time": None},
        {"event_time_end": datetime(2026, 9, 23, tzinfo=UTC)},
        {"time_precision": TimePrecision.RANGE},
        {
            "time_precision": TimePrecision.RANGE,
            "event_time_end": datetime(2026, 9, 21, tzinfo=UTC),
        },
        {"event_time": datetime(2026, 9, 22)},  # noqa: DTZ001 - naive on purpose
        {"confidence": 1.2},
        {"location_unlocode": "Valencia"},
        {"equipment": ("CSQU3054384",)},
        {"field": "Vessel Departure"},
        {"source_role": SourceRole.HUMAN_REVIEW},
        {"status": ObservationStatus.SUPERSEDED},
        {"status": ObservationStatus.REJECTED},
        {"unknown_field": 1},
    ],
)
def test_invalid_observations(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        observation(**overrides)


def test_range_and_superseded_and_human_observations() -> None:
    window = observation(
        event_type=EventType.STUFFING,
        classifier=EventClassifier.PLANNED,
        field="stuffing.time",
        time_precision=TimePrecision.RANGE,
        event_time_end=datetime(2026, 9, 25, tzinfo=UTC),
        source_role=SourceRole.HAULIER,
    )
    assert window.event_time_end is not None
    superseded = observation(
        status=ObservationStatus.SUPERSEDED, superseded_by="obs-9", superseded_at=T0
    )
    assert superseded.status is ObservationStatus.SUPERSEDED
    human = observation(
        source_role=SourceRole.HUMAN_REVIEW,
        classifier=EventClassifier.ACTUAL,
        provenance=Provenance(
            tier=ExtractionTier.HUMAN, extractor_version="ui", config_version="c1"
        ),
    )
    assert human.provenance.tier is ExtractionTier.HUMAN


def test_evidence_span() -> None:
    with pytest.raises(ValidationError):
        Evidence(text="ETD", start=10, end=10)
    with pytest.raises(ValidationError):
        Evidence(text="", start=0, end=1)


def test_field_state_needs_its_winner() -> None:
    common: dict[str, Any] = {
        "shipment_id": "shp-1",
        "field": "vessel_departure.time",
        "rule": "fresh_ab",
        "computed_at": T0,
        "config_version": "c1",
    }
    FieldState(value=None, winning_observation_id=None, **common)
    FieldState(value="2026-09-22", winning_observation_id="obs-1", **common)
    with pytest.raises(ValidationError):
        FieldState(value="2026-09-22", winning_observation_id=None, **common)


@pytest.mark.parametrize(
    ("action", "new_value", "reason", "valid"),
    [
        (CorrectionAction.ACCEPT, None, None, True),
        (CorrectionAction.CORRECT, "2026-09-23", None, True),
        (CorrectionAction.REJECT, None, "valor de otro expediente", True),
        (CorrectionAction.CORRECT, None, None, False),
        (CorrectionAction.ACCEPT, "2026-09-23", None, False),
        (CorrectionAction.REJECT, None, None, False),
    ],
)
def test_correction_rules(
    action: CorrectionAction, new_value: str | None, reason: str | None, *, valid: bool
) -> None:
    def build() -> Correction:
        return Correction(
            correction_id="c-1",
            task_id="t-1",
            user_id="u-1",
            action=action,
            new_value=new_value,
            reason=reason,
            created_at=T0,
        )

    if valid:
        assert build().action is action
    else:
        with pytest.raises(ValidationError):
            build()
