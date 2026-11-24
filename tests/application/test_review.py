"""Operators' decisions on the synthetic set: they add or supersede, and the verdict follows."""

from zoneinfo import ZoneInfo

import pytest

from eshipping_ai.application.review import ApplyCorrection, Decision, ReviewError
from eshipping_ai.domain.vocabulary import (
    CorrectionAction,
    EventClassifier,
    ExtractionTier,
    ObservationStatus,
    SourceRole,
)
from tests.application.test_process import Pipeline
from tests.builders import CONFIG

MADRID = ZoneInfo("Europe/Madrid")


@pytest.fixture
def reviewed(pipeline: Pipeline) -> Pipeline:
    pipeline.process()
    pipeline.reconcile()
    return pipeline


def apply(pipeline: Pipeline, decision: Decision) -> None:
    ApplyCorrection(pipeline.repo, pipeline.repo, pipeline.clock, CONFIG, MADRID).apply(decision)
    pipeline.reconcile()


def verdict(pipeline: Pipeline, shipment: str, field: str) -> tuple[str, str | None]:
    (found,) = [v for v in pipeline.repo.verdicts_for(shipment) if v.field == field]
    return found.code.value, found.mail_value


def test_a_correction_is_a_human_observation_that_wins(reviewed: Pipeline) -> None:
    assert verdict(reviewed, "ES26900002", "vessel_departure") == ("DISCREPANCY", "2026-10-06")
    apply(
        reviewed,
        Decision(
            "ES26900002",
            "vessel_departure",
            CorrectionAction.CORRECT,
            "op1",
            value="2026-10-01",
            reason="La naviera confirma por teléfono",
            classifier=EventClassifier.ACTUAL,
        ),
    )
    assert verdict(reviewed, "ES26900002", "vessel_departure") == ("MATCH", "2026-10-01")
    (human,) = [
        o
        for o in reviewed.repo.observations_for("ES26900002")
        if o.provenance.tier is ExtractionTier.HUMAN
    ]
    assert human.source_role is SourceRole.HUMAN_REVIEW
    assert human.evidence.text == "La naviera confirma por teléfono"
    assert human.message_id is not None and human.message_id.startswith("correction:")


def test_accepting_keeps_the_value_with_human_authority(reviewed: Pipeline) -> None:
    apply(reviewed, Decision("ES26900002", "vessel", CorrectionAction.ACCEPT, "op1"))
    assert verdict(reviewed, "ES26900002", "vessel") == ("DISCREPANCY", "CELESTE FICTICIA")
    states = {s.field: s for s in reviewed.repo.field_states_for("ES26900002")}
    assert states["vessel"].rule == "human_review"


def test_rejecting_supersedes_the_winner_and_the_next_value_takes_its_place(
    reviewed: Pipeline,
) -> None:
    apply(reviewed, Decision("ES26900002", "vessel", CorrectionAction.REJECT, "op1", reason="x"))
    assert verdict(reviewed, "ES26900002", "vessel") == ("MATCH", "BOREAL FICTICIA")
    statuses = {
        o.value: o.status
        for o in reviewed.repo.observations_for("ES26900002")
        if o.field == "vessel"
    }
    assert statuses["CELESTE FICTICIA"] is ObservationStatus.SUPERSEDED


@pytest.mark.parametrize(
    ("decision", "message"),
    [
        (Decision("ES26900001", "colour", CorrectionAction.ACCEPT, "op"), "unknown field"),
        (Decision("ES26900001", "vessel", CorrectionAction.REJECT, "op"), "reason"),
        (Decision("ES26900001", "vessel", CorrectionAction.CORRECT, "op"), "new value"),
        (
            Decision("ES26900001", "bill_of_lading", CorrectionAction.REJECT, "op", reason="x"),
            "reject",
        ),
        (Decision("ES26900001", "bill_of_lading", CorrectionAction.ACCEPT, "op"), "accept"),
        (
            Decision("ES26900001", "stuffing", CorrectionAction.CORRECT, "op", value="mañana"),
            "YYYY-MM-DD",
        ),
        (
            Decision("ES26900001", "equipment_count", CorrectionAction.CORRECT, "op", value="dos"),
            "whole number",
        ),
    ],
)
def test_decisions_that_do_not_fit_are_refused(
    reviewed: Pipeline, decision: Decision, message: str
) -> None:
    with pytest.raises(ReviewError, match=message):
        ApplyCorrection(reviewed.repo, reviewed.repo, reviewed.clock, CONFIG, MADRID).apply(
            decision
        )
