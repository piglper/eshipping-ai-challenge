"""The reconciliation, fed with the perfect extraction of the synthetic gold, gives its verdicts."""

import json
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from eshipping_ai.adapters.erp_csv import CsvErpGateway
from eshipping_ai.application.reconcile import ReconcileShipments
from eshipping_ai.domain.model import ErpRecord, ErpSnapshot, FieldState, Observation, Verdict
from eshipping_ai.domain.vocabulary import (
    EventClassifier,
    EventType,
    Priority,
    SourceRole,
    TimePrecision,
    VerdictCode,
)
from eshipping_ai.synthetic.spec import load_spec
from tests.builders import CONFIG, NOW, observation
from tests.conftest import SPEC_PATH

ROLE_OF_PARTY = {
    "carrier": SourceRole.CARRIER,
    "haulier": SourceRole.HAULIER,
    "customs": SourceRole.CUSTOMS_AGENT,
    "ops": SourceRole.INTERNAL,
    "customer3": SourceRole.CUSTOMER,
    "unknown": SourceRole.CUSTOMER,
}
GOLD_TO_FIELDS = {
    "booking": ["booking"],
    "vessel": ["vessel"],
    "vessel_departure": ["vessel_departure"],
    "vessel_arrival_pod": ["vessel_arrival_pod"],
    "stuffing": ["stuffing"],
    "customs_release": ["customs_release"],
    "cutoff": ["cutoff_document", "cutoff_vgm", "cutoff_full"],
    "equipment": ["equipment_count"],
}
CUTOFFS = {"DCO": "cutoff_document", "VCO": "cutoff_vgm", "FCO": "cutoff_full"}


class MemoryObservations:
    def __init__(self, observations: Sequence[Observation]) -> None:
        self._observations = list(observations)

    def add_observations(self, observations):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def observations_for(self, shipment_id: str, as_of: datetime | None = None):  # type: ignore[no-untyped-def]
        return [o for o in self._observations if o.shipment_id == shipment_id]


class MemoryProjections:
    def __init__(self) -> None:
        self.states: list[FieldState] = []
        self.verdicts: list[Verdict] = []

    def save_field_states(self, states):  # type: ignore[no-untyped-def]
        self.states.extend(states)

    def save_verdicts(self, verdicts):  # type: ignore[no-untyped-def]
        self.verdicts.extend(verdicts)


class MemoryErpStore:
    def __init__(self) -> None:
        self.snapshots: list[ErpSnapshot] = []

    def add_erp_snapshot(self, snapshot: ErpSnapshot, records: Sequence[ErpRecord]) -> None:
        self.snapshots.append(snapshot)


class RecordingNotifier:
    def __init__(self) -> None:
        self.notices: list[tuple[str, list[Verdict]]] = []

    def notify(self, shipment_id: str, verdicts: Sequence[Verdict]) -> None:
        self.notices.append((shipment_id, list(verdicts)))


def gold_observations(
    synthetic_dir: Path,
) -> tuple[list[Observation], dict[str, str], dict[str, Any]]:
    """What a perfect extraction of the synthetic mails would give, from the gold itself."""
    spec = load_spec(SPEC_PATH)
    gold = json.loads((synthetic_dir / "gold.json").read_text(encoding="utf-8"))["expedientes"]
    observations: list[Observation] = []
    for shipment in spec.shipments:
        role_by_mail = {m.id: ROLE_OF_PARTY[m.sender] for m in shipment.mails}
        for name, expected in gold[shipment.operation].items():
            if expected["source"] is None:
                continue
            observations += _from_gold(shipment.operation, name, expected, role_by_mail)
    observations += _extra_observations()
    return observations, {s.operation: s.operation for s in spec.shipments}, gold


def _from_gold(op: str, name: str, expected: dict[str, Any], roles: dict[str, SourceRole]):  # type: ignore[no-untyped-def]
    common: dict[str, Any] = {
        "shipment": op,
        "role": roles[expected["source"]],
        "known": expected.get("known_at") or "2026-09-20",
        "classifier": EventClassifier(expected.get("classifier") or "EST"),
    }
    value = expected["value"]
    if name == "stuffing":
        start, _, end = value["date"].partition("/")
        yield observation(
            "stuffing",
            start,
            end=end or None,
            precision=TimePrecision.RANGE if end else None,
            **common,
        )
    elif name == "cutoff":
        for code, text in value.items():
            yield observation(CUTOFFS[code], text[:10], **common)
    elif name == "equipment":
        yield observation("equipment_count", str(value["count"]), **common)
    elif name == "vessel":
        event = EventType.VESSEL_CHANGE if op == "ES26900002" else EventType.DEPARTURE
        yield observation("vessel", value, event_type=event, **common)
    else:
        yield observation(name, value, **common)


def _extra_observations() -> list[Observation]:
    return [
        # ES26900002: the booking that the rollover replaced is an alias of the new one.
        observation("booking", "990000202", shipment="ES26900002", known="2026-09-15"),
        # ES26900003: the customer's own arrival date must wait for confirmation (rank C).
        observation(
            "vessel_arrival_pod",
            "2026-11-02",
            shipment="ES26900003",
            role=SourceRole.CUSTOMER,
            known="2026-10-05",
        ),
    ]


def run(synthetic_dir: Path, clock):  # type: ignore[no-untyped-def]
    observations, shipments, gold = gold_observations(synthetic_dir)
    projections, notifier = MemoryProjections(), RecordingNotifier()
    use_case = ReconcileShipments(
        CsvErpGateway(synthetic_dir / "erp.csv", NOW),
        MemoryErpStore(),
        MemoryObservations(observations),
        projections,
        notifier,
        clock,
        CONFIG,
    )
    return use_case.run(shipments), projections, notifier, gold


def test_the_verdicts_are_the_ones_of_the_gold(synthetic_dir, clock):  # type: ignore[no-untyped-def]
    _, projections, _, gold = run(synthetic_dir, clock)
    got = {(v.shipment_id, v.field): v.code.value for v in projections.verdicts}
    for operation, fields in gold.items():
        for name, expected in fields.items():
            codes = {got[(operation, f)] for f in GOLD_TO_FIELDS[name] if (operation, f) in got}
            assert codes == {expected["verdict"]}, (operation, name, codes)


def test_all_seven_verdicts_appear_and_the_report_counts_them(synthetic_dir, clock):  # type: ignore[no-untyped-def]
    report, projections, _, _ = run(synthetic_dir, clock)
    assert set(report.verdicts) == {code.value for code in VerdictCode}
    assert sum(report.verdicts.values()) == len(projections.verdicts)
    assert report.shipments == 4 and report.not_in_erp == 0
    # The day-month typo in ES26900003 leaves both the stuffing and the customs release
    # after the departure: two rules broken by the same wrong date.
    assert report.quality_issues == 2
    assert Counter(s.shipment_id for s in projections.states)["ES26900001"] == len(CONFIG.fields)


def test_priorities_and_notices(synthetic_dir, clock):  # type: ignore[no-untyped-def]
    report, projections, notifier, _ = run(synthetic_dir, clock)
    by_key = {(v.shipment_id, v.field): v for v in projections.verdicts}
    assert by_key[("ES26900002", "vessel")].priority is Priority.P1  # rollover
    assert by_key[("ES26900003", "vessel_departure")].priority is Priority.P2
    assert by_key[("ES26900001", "customs_release")].priority is Priority.P3
    assert by_key[("ES26900004", "vessel_departure")].priority is None  # ERP_NEWER needs no review
    assert [(s, [v.field for v in vs]) for s, vs in notifier.notices] == [
        ("ES26900002", ["vessel"])
    ]
    assert report.urgent == 1


def test_the_informative_source_waits_for_confirmation(synthetic_dir, clock):  # type: ignore[no-untyped-def]
    _, projections, _, _ = run(synthetic_dir, clock)
    state = next(
        s
        for s in projections.states
        if (s.shipment_id, s.field) == ("ES26900003", "vessel_arrival_pod")
    )
    assert state.value == "2026-10-27" and len(state.pending_confirmation) == 1


def test_a_shipment_missing_from_the_erp_is_counted(synthetic_dir, clock):  # type: ignore[no-untyped-def]
    observations, shipments, _ = gold_observations(synthetic_dir)
    projections = MemoryProjections()
    report = ReconcileShipments(
        CsvErpGateway(synthetic_dir / "erp.csv", NOW),
        MemoryErpStore(),
        MemoryObservations(observations),
        projections,
        RecordingNotifier(),
        clock,
        CONFIG,
    ).run({"shp-x": "ES29999999", **shipments})
    assert report.not_in_erp == 1 and report.shipments == 5
