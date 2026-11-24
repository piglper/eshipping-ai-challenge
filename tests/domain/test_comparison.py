from datetime import date, timedelta

import pytest

from eshipping_ai.domain.comparison import (
    ComparisonInput,
    _is_typo,
    compare_field,
    erp_quality_issues,
)
from eshipping_ai.domain.policy import project_field
from eshipping_ai.domain.vocabulary import (
    EventClassifier,
    EventType,
    Priority,
    SourceRole,
    TimePrecision,
    VerdictCode,
)
from tests.builders import CONFIG, NOW, at, erp_row, observation

DEP = "vessel_departure"
ACT, EST = EventClassifier.ACTUAL, EventClassifier.ESTIMATED


def compare(field, observations, erp, *, read_at=None, last_known=None):  # type: ignore[no-untyped-def]
    state = project_field("shp-1", field, observations, CONFIG, NOW)
    winner = next(
        (o for o in observations if o.observation_id == state.winning_observation_id), None
    )
    history = {o.value for o in observations if field == "booking" and o is not winner}
    return compare_field(
        ComparisonInput(
            shipment_id="shp-1",
            field=field,
            rule=CONFIG.fields[field],
            config=CONFIG,
            state=state,
            winner=winner,
            history=history,
            erp=erp,
            erp_read_at=read_at or NOW,
            last_mail_known_at=last_known,
            issues=erp_quality_issues(erp),
            now=NOW,
        )
    )


def test_match_with_tolerance_ranges_and_approximate_dates() -> None:
    erp = erp_row(vessel_departure="2026-10-08")
    assert compare(DEP, [observation(DEP, "2026-10-08")], erp).code is VerdictCode.MATCH
    window = observation(DEP, "2026-10-07", precision=TimePrecision.RANGE, end="2026-10-10")
    assert compare(DEP, [window], erp).code is VerdictCode.MATCH
    approx = observation(DEP, "2026-10-06", precision=TimePrecision.APPROX)
    assert compare(DEP, [approx], erp).code is VerdictCode.MATCH
    far = observation(DEP, "2026-10-04", precision=TimePrecision.APPROX)
    assert compare(DEP, [far], erp).code is VerdictCode.DISCREPANCY


def test_booking_matches_through_an_alias_and_vessel_names_are_normalised() -> None:
    erp = erp_row(booking="990000202", vessel="BOREAL FICTICIA")
    replaced = [
        observation("booking", "990000202", known="2026-09-15"),
        observation("booking", "990000203", known="2026-09-29"),
    ]
    assert compare("booking", replaced, erp).code is VerdictCode.MATCH
    assert compare("booking", replaced[1:], erp).code is VerdictCode.DISCREPANCY
    same = observation("vessel", "M/V Boreal  Ficticia")
    assert compare("vessel", [same], erp).code is VerdictCode.MATCH
    other = observation("vessel", "CELESTE FICTICIA")
    assert compare("vessel", [other], erp).code is VerdictCode.DISCREPANCY


def test_erp_missing_mail_missing_and_not_in_erp() -> None:
    mail = observation("customs_release", "2026-10-06", role=SourceRole.CUSTOMS_DOC, classifier=ACT)
    missing = compare("customs_release", [mail], erp_row())
    assert (missing.code, missing.priority) == (VerdictCode.ERP_MISSING, Priority.P3)
    assert compare("customs_release", [], erp_row(customs_release="2026-10-01")).code is (
        VerdictCode.MAIL_MISSING
    )
    assert compare("customs_release", [], erp_row()) is None
    cutoff = observation("cutoff_full", "2026-10-06")
    assert compare("cutoff_full", [cutoff], erp_row()).code is VerdictCode.NOT_IN_ERP


def test_rule_a_the_erp_is_newer_when_it_says_actual_after_the_last_mail() -> None:
    mail = observation(DEP, "2026-09-25", known="2026-09-10")
    erp = erp_row(vessel_departure="2026-09-27", vessel_departure_actual="true")
    verdict = compare(DEP, [mail], erp, last_known=at("2026-09-20"))
    assert (verdict.code, verdict.rule, verdict.priority) == (
        VerdictCode.ERP_NEWER,
        "rule_a_erp_newer",
        None,
    )
    estimated = erp_row(vessel_departure="2026-09-27", vessel_departure_actual="false")
    assert compare(DEP, [mail], estimated, last_known=at("2026-09-20")).code is (
        VerdictCode.DISCREPANCY
    )
    earlier = erp_row(vessel_departure="2026-09-27", vessel_departure_actual="true")
    assert compare(DEP, [mail], earlier, last_known=at("2026-09-30")).code is (
        VerdictCode.DISCREPANCY
    )


def test_rule_a_with_a_known_update_time_of_the_erp_field() -> None:
    mail = observation(DEP, "2026-09-25", known="2026-09-10")
    newer = erp_row(vessel_departure="2026-09-26", updated={"vessel_departure": at("2026-09-15")})
    assert compare(DEP, [mail], newer).code is VerdictCode.ERP_NEWER
    older = erp_row(vessel_departure="2026-09-26", updated={"vessel_departure": at("2026-09-05")})
    assert compare(DEP, [mail], older).code is VerdictCode.ERP_ERROR


def test_rule_b_a_clear_error_needs_authority_confidence_and_a_reason() -> None:
    sailed = observation(DEP, "2026-10-04", classifier=ACT, known="2026-10-04")
    typo = erp_row(vessel_departure="2026-04-10", vessel_departure_actual="true")
    verdict = compare(DEP, [sailed], typo)
    assert (verdict.code, verdict.rule) == (VerdictCode.ERP_ERROR, "rule_b_clear_error")
    low = observation(DEP, "2026-10-04", classifier=ACT, known="2026-10-04", confidence=0.5)
    assert compare(DEP, [low], typo).code is VerdictCode.DISCREPANCY  # below the field threshold
    plain = erp_row(vessel_departure="2026-10-20")
    assert compare(DEP, [sailed], plain).code is VerdictCode.DISCREPANCY
    internal = observation(DEP, "2026-10-04", classifier=ACT, role=SourceRole.INTERNAL)
    assert compare(DEP, [internal], erp_row(vessel_departure="2026-10-05")).code is (
        VerdictCode.DISCREPANCY
    )


def test_a_typo_alone_is_enough_for_an_actual_date_but_not_for_an_estimate() -> None:
    erp = erp_row(vessel_departure="2026-04-10")
    sailed = observation(DEP, "2026-10-04", classifier=ACT)
    assert compare(DEP, [sailed], erp).code is VerdictCode.ERP_ERROR
    # the same swap against an estimate is only a discrepancy: nothing says the ERP is wrong
    estimate = compare(
        DEP, [observation(DEP, "2026-10-04")], erp_row(vessel_departure="2026-04-10")
    )
    assert estimate.code is VerdictCode.DISCREPANCY


@pytest.mark.parametrize(
    ("mail", "erp", "typo"),
    [
        (date(2026, 10, 4), date(2026, 4, 10), True),
        (date(2026, 10, 12), date(2026, 10, 21), True),
        (date(2026, 10, 12), date(2026, 10, 13), False),
        (date(2026, 10, 11), date(2026, 11, 10), True),
        (date(2026, 10, 10), date(2026, 10, 10), False),
        (date(2026, 10, 4), date(2026, 10, 24), False),
    ],
)
def test_typo_detection(mail: date, erp: date, typo: bool) -> None:
    assert _is_typo(mail, erp) is typo


def test_a_stale_erp_read_gives_no_proposals() -> None:
    old = NOW - timedelta(hours=30)
    mail = observation("customs_release", "2026-10-06", role=SourceRole.CUSTOMS_DOC)
    verdict = compare("customs_release", [mail], erp_row(), read_at=old)
    assert (verdict.code, verdict.rule) == (VerdictCode.DISCREPANCY, "stale_erp_read")
    sailed = observation(DEP, "2026-10-04", classifier=ACT)
    stale = compare(DEP, [sailed], erp_row(vessel_departure="2026-04-10"), read_at=old)
    assert stale.code is VerdictCode.DISCREPANCY


def test_a_field_in_conflict_is_not_compared() -> None:
    conflict = [
        observation(DEP, "2026-10-04", classifier=ACT, known="2026-10-04"),
        observation(DEP, "2026-10-05", classifier=ACT, known="2026-10-06"),
    ]
    assert compare(DEP, conflict, erp_row(vessel_departure="2026-10-04")) is None


def test_priorities() -> None:
    erp = erp_row(vessel_departure="2026-10-20")
    soon = observation(DEP, "2026-10-09", known="2026-10-01")
    assert compare(DEP, [soon], erp).priority is Priority.P1
    later = observation(DEP, "2026-10-12", known="2026-10-01")
    assert compare(DEP, [later], erp).priority is Priority.P2
    past = observation(DEP, "2026-10-03", known="2026-10-01")
    assert compare(DEP, [past], erp).priority is Priority.P2
    rolled = observation(
        "vessel", "CELESTE", event_type=EventType.VESSEL_CHANGE, known="2026-10-01"
    )
    assert compare("vessel", [rolled], erp_row(vessel="BOREAL")).priority is Priority.P1
    minor = observation("equipment_count", "2", role=SourceRole.CARRIER)
    assert compare("equipment_count", [minor], erp_row(equipment_count="3")).priority is Priority.P3
    match = observation(DEP, "2026-10-20")
    assert compare(DEP, [match], erp).priority is None


def test_erp_internal_coherence() -> None:
    bad = erp_row(
        vessel_departure="2026-10-01",
        vessel_arrival_pod="2026-09-20",
        stuffing="2026-10-05",
        customs_release="2026-10-03",
    )
    assert erp_quality_issues(bad) == {
        "vessel_arrival_pod": "departure_after_arrival",
        "vessel_departure": "stuffing_after_departure",
        "customs_release": "release_after_departure",
    }
    assert erp_quality_issues(erp_row(vessel_departure="2026-10-01", stuffing="2026-09-28")) == {}
    assert erp_quality_issues(erp_row(vessel_departure="no-date")) == {}
