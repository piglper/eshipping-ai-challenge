import pytest

from eshipping_ai.domain.policy import project_field, rank_for
from eshipping_ai.domain.vocabulary import (
    EventClassifier,
    ObservationStatus,
    SourceRank,
    SourceRole,
    Zone,
)
from tests.builders import CONFIG, NOW, observation

DEP = "vessel_departure"
ACT, EST = EventClassifier.ACTUAL, EventClassifier.ESTIMATED


def project(*observations, field: str = DEP):  # type: ignore[no-untyped-def]
    return project_field("shp-1", field, observations, CONFIG, NOW)


@pytest.mark.parametrize(
    ("field", "role", "rank"),
    [
        (DEP, SourceRole.CARRIER, SourceRank.A),
        (DEP, SourceRole.INTERNAL, SourceRank.B),
        (DEP, SourceRole.CUSTOMER, SourceRank.C),
        (DEP, SourceRole.HAULIER, SourceRank.C),
        ("stuffing", SourceRole.HAULIER, SourceRank.A),
        ("customs_release", SourceRole.CUSTOMS_DOC, SourceRank.A),
        (DEP, SourceRole.HUMAN_REVIEW, SourceRank.A),
        ("unknown_field", SourceRole.CARRIER, SourceRank.C),
    ],
)
def test_rank_depends_on_the_field(field: str, role: SourceRole, rank: SourceRank) -> None:
    assert rank_for(CONFIG, field, role) is rank


def test_no_observations() -> None:
    state = project()
    assert (state.value, state.rule, state.in_conflict) == (None, "no_observations", False)


def test_the_freshest_reliable_source_wins_and_the_history_is_kept() -> None:
    old = observation(DEP, "2026-10-01", known="2026-09-15")
    new = observation(DEP, "2026-10-06", known="2026-09-20", role=SourceRole.INTERNAL)
    state = project(old, new)
    assert (state.value, state.rule) == ("2026-10-06", "freshest_reliable")
    assert state.winning_observation_id == new.observation_id


def test_an_actual_value_beats_a_later_estimate() -> None:
    sailed = observation(DEP, "2026-10-04", classifier=ACT, known="2026-10-04")
    later_estimate = observation(DEP, "2026-10-08", classifier=EST, known="2026-10-05")
    state = project(sailed, later_estimate)
    assert (state.value, state.rule) == ("2026-10-04", "actual_over_estimate")


def test_two_different_actuals_are_a_conflict() -> None:
    state = project(
        observation(DEP, "2026-10-04", classifier=ACT, known="2026-10-04"),
        observation(DEP, "2026-10-05", classifier=ACT, known="2026-10-06"),
    )
    assert (state.value, state.in_conflict, state.rule) == (None, True, "conflicting_actuals")
    assert len(state.pending_confirmation) == 2


def test_a_conflict_inside_the_window_and_none_outside() -> None:
    inside = project(
        observation(DEP, "2026-10-01", known="2026-09-20", known_hour=10),
        observation(DEP, "2026-10-06", known="2026-09-21", known_hour=9),
    )
    outside = project(
        observation(DEP, "2026-10-01", known="2026-09-20", known_hour=10),
        observation(DEP, "2026-10-06", known="2026-09-21", known_hour=12),
    )
    assert inside.in_conflict and not outside.in_conflict
    assert outside.value == "2026-10-06"


def test_an_informative_source_never_replaces_the_current_value() -> None:
    carrier = observation(DEP, "2026-10-06", known="2026-09-15")
    customer = observation(DEP, "2026-10-09", known="2026-09-20", role=SourceRole.CUSTOMER)
    state = project(carrier, customer)
    assert state.value == "2026-10-06"
    assert state.pending_confirmation == (customer.observation_id,)


def test_only_informative_sources_leave_the_field_pending() -> None:
    customer = observation(DEP, "2026-10-09", role=SourceRole.CUSTOMER)
    state = project(customer)
    assert (state.value, state.rule) == (None, "only_informative")
    assert state.pending_confirmation == (customer.observation_id,)


def test_a_human_review_prevails_but_flags_a_later_contradiction() -> None:
    human = observation(
        DEP, "2026-10-03", role=SourceRole.HUMAN_REVIEW, classifier=ACT, known="2026-10-03"
    )
    later_carrier = observation(DEP, "2026-10-05", known="2026-10-04")
    state = project(human, later_carrier)
    assert (state.value, state.rule) == ("2026-10-03", "human_review")
    assert state.pending_confirmation == (later_carrier.observation_id,)
    assert not state.in_conflict


def test_discarded_observations_and_other_fields_are_ignored() -> None:
    superseded = observation(
        DEP,
        "2026-10-01",
        status=ObservationStatus.SUPERSEDED,
        superseded_by="x",
        superseded_at=NOW,
    )
    unproposed = observation(DEP, "2026-10-02", zone=Zone.NOT_PROPOSED)
    other_shipment = observation(DEP, "2026-10-03", shipment="shp-2")
    other_field = observation("vessel_arrival_pod", "2026-10-30")
    assert project(superseded, unproposed, other_shipment, other_field).rule == "no_observations"
