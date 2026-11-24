"""Builders of valid synthetic observations and ERP rows for the policy tests."""

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from eshipping_ai.adapters.config_yaml import load_reconciliation_config
from eshipping_ai.domain.model import ErpRecord, Evidence, Observation, Provenance
from eshipping_ai.domain.policy import ReconciliationConfig, rank_for
from eshipping_ai.domain.vocabulary import (
    EventClassifier,
    EventType,
    ExtractionTier,
    SourceRole,
    TimePrecision,
    Zone,
)

CONFIG_PATH = Path(__file__).parents[1] / "config" / "reconciliation.yaml"
CONFIG: ReconciliationConfig = load_reconciliation_config(CONFIG_PATH)
MADRID = timezone(timedelta(hours=2))
NOW = datetime(2026, 10, 7, 8, 0, tzinfo=MADRID)


def at(day: str, hour: int = 12) -> datetime:
    """A moment of a day, in local summer time."""
    return datetime.combine(date.fromisoformat(day), time(hour), tzinfo=MADRID)


def observation(  # noqa: PLR0913 - a builder with one knob per attribute
    field: str,
    value: str,
    *,
    classifier: EventClassifier = EventClassifier.ESTIMATED,
    role: SourceRole = SourceRole.CARRIER,
    known: str = "2026-09-20",
    known_hour: int = 12,
    shipment: str = "shp-1",
    event_type: EventType = EventType.DEPARTURE,
    precision: TimePrecision | None = None,
    end: str | None = None,
    confidence: float = 0.97,
    zone: Zone = Zone.AUTO,
    **extra: Any,
) -> Observation:
    """Build an observation; dates in ``value`` become ``event_time`` automatically."""
    kind = CONFIG.fields[field].kind if field in CONFIG.fields else "text"
    event_time = None
    if kind == "date" and precision is None:
        precision = TimePrecision.DATE
    if kind == "date":
        event_time = at(value[:10], 0)
    tier = ExtractionTier.HUMAN if role is SourceRole.HUMAN_REVIEW else ExtractionTier.RULE
    data: dict[str, Any] = {
        "observation_id": f"obs-{field}-{value}-{known}-{role}-{classifier}",
        "shipment_id": shipment,
        "message_id": "msg-1",
        "event_type": event_type,
        "classifier": classifier,
        "field": field,
        "value": value,
        "value_raw": value,
        "event_time": event_time,
        "event_time_end": at(end, 0) if end else None,
        "time_precision": precision if kind == "date" else None,
        "source_role": role,
        "source_rank": rank_for(CONFIG, field, role),
        "evidence": Evidence(text=value, start=0, end=len(value)),
        "known_at": at(known, known_hour),
        "recorded_at": at(known, known_hour) + timedelta(minutes=1),
        "provenance": Provenance(tier=tier, extractor_version="1", config_version="c1"),
        "confidence": confidence,
        "zone": zone,
    }
    data.update(extra)
    return Observation(**data)


def erp_row(updated: dict[str, datetime] | None = None, **normalized: str | None) -> ErpRecord:
    """An ERP row with the given normalised fields; the rest are empty."""
    keys = {
        "operation",
        "booking",
        "vessel",
        "vessel_departure",
        "vessel_departure_actual",
        "vessel_arrival_pod",
        "vessel_arrival_actual",
        "stuffing",
        "customs_release",
        "equipment_count",
    }
    fields = dict.fromkeys(keys) | normalized
    return ErpRecord(
        snapshot_id="erp-1",
        operation="ES26900001",
        raw={},
        normalized=fields,
        field_updated_at=updated or {},
    )
