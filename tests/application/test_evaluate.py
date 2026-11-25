import pytest

from eshipping_ai.application.evaluate import (
    NO_VERDICT,
    NOISE_KEY,
    Extracted,
    Score,
    evaluate_fields,
    evaluate_mails,
    evaluate_verdicts,
    total_score,
    values_agree,
    wilson_interval,
)
from eshipping_ai.domain.model import Verdict
from eshipping_ai.domain.ports import MailOutcome
from eshipping_ai.domain.vocabulary import AssociationStatus, MailClass, VerdictCode
from tests.builders import NOW

AUTO, REVIEW = AssociationStatus.AUTO, AssociationStatus.IN_REVIEW


def verdict(field: str, code: VerdictCode) -> Verdict:
    return Verdict(
        verdict_id=f"v-{field}",
        shipment_id="S1",
        field=field,
        code=code,
        mail_value=None,
        erp_value=None,
        erp_record=None,
        rule="r",
        computed_at=NOW,
        config_version="c",
    )


def outcome(
    source: str,
    position: int | None,
    classes: tuple[MailClass, ...],
    shipments: tuple[tuple[str, AssociationStatus], ...] = (),
) -> MailOutcome:
    return MailOutcome(
        mail_id=f"mail-{source}-{position}",
        source_ref=source,
        position=position,
        classes=classes,
        shipments=shipments,
    )


# --- measures ---------------------------------------------------------------------------


def test_the_wilson_interval_gives_the_limits_of_the_reliability_document() -> None:
    # docs/07_fiabilidad.md §6.1: with no error, 38 cases reach 90.8 % and 89 cases 95.9 %.
    assert wilson_interval(38, 38)[0] == pytest.approx(0.908, abs=0.001)
    assert wilson_interval(89, 89)[0] == pytest.approx(0.959, abs=0.001)
    assert wilson_interval(0, 0) == (0.0, 1.0)
    low, high = wilson_interval(5, 10)
    assert low < 0.5 < high


def test_a_score_counts_a_wrong_value_as_both_errors() -> None:
    score = Score()
    score.count(expected=True, given=True, right=True)
    score.count(expected=True, given=True, right=False)
    score.count(expected=True, given=False, right=False)
    score.count(expected=False, given=True, right=False)
    score.count(expected=False, given=False, right=False)
    assert (score.tp, score.fp, score.fn) == (1, 2, 2)
    assert score.precision == score.recall == score.f1 == pytest.approx(1 / 3)
    assert Score().f1 == 0.0
    assert total_score({"a": score, "b": Score(tp=3)}).tp == 4


@pytest.mark.parametrize(
    ("field", "expected", "got", "tolerance", "agree"),
    [
        ("booking", "990000101", "990-000-101", 0, True),
        ("booking", "990000101", "990000102", 0, False),
        ("vessel", "AURORA FICTICIA", "M/V Aurora  Ficticia", 0, True),
        ("vessel_departure", "2026-10-08", "2026-10-08", 0, True),
        ("vessel_departure", "2026-10-08", "2026-10-09", 0, False),
        ("vessel_departure", "2026-10-08", "2026-10-09", 1, True),
        ("cutoff", "2026-10-05 12:00", "2026-10-05", 0, True),
        ("stuffing", "2026-09-29/2026-09-30", "2026-09-29/2026-09-30", 0, True),
        ("stuffing", "2026-09-29/2026-09-30", "2026-09-29", 0, False),
        ("customs_release", "2026-10-06", "pronto", 0, False),
        ("equipment", "2", "2", 0, True),
    ],
)
def test_values_agree(field: str, expected: str, got: str, tolerance: int, agree: bool) -> None:
    assert values_agree(field, expected, got, tolerance) is agree


# --- fields -----------------------------------------------------------------------------


def test_fields_are_scored_with_their_classifier() -> None:
    gold = {
        "S1": {
            "vessel": {"value": "AURORA FICTICIA"},
            "vessel_departure": {"value": "2026-10-08", "classifier": "EST"},
            "vessel_arrival_pod": {"value": "2026-10-24", "classifier": "EST"},
            "stuffing": {"value": None, "verdict": "MAIL_MISSING"},
            "equipment": {"value": {"count": 2, "type": "20DV"}},
            "incidents": {"value": []},
        }
    }
    extracted = {
        "S1": {
            "vessel": Extracted("AURORA FICTICIA", "PLN"),
            "vessel_departure": Extracted("2026-10-08", "ACT"),
            "vessel_arrival_pod": Extracted("2026-10-25", "EST"),
            "stuffing": Extracted("2026-09-30", "PLN"),
            "equipment_count": Extracted("2", None),
            "customs_release": Extracted("2026-10-06", "ACT"),
        }
    }
    evaluation = evaluate_fields(gold, extracted)
    scores = evaluation.scores
    assert (scores["vessel"].tp, scores["equipment"].tp) == (1, 1)
    assert (scores["vessel_arrival_pod"].fp, scores["vessel_arrival_pod"].fn) == (1, 1)
    assert (scores["stuffing"].fp, scores["stuffing"].fn) == (1, 0)
    assert "customs_release" not in scores  # the gold says nothing of it for this shipment
    assert evaluation.classifier["vessel_departure"].rate == 0.0
    assert "vessel_arrival_pod" not in evaluation.classifier  # wrong values are not scored
    assert {m.field for m in evaluation.mismatches} == {"vessel_arrival_pod", "stuffing"}


def test_cutoffs_are_paired_by_kind_and_an_unsure_kind_takes_any() -> None:
    gold = {"S1": {"cutoff": {"value": {"VCO": "2026-10-05 12:00", "FCO?": "2026-10-06 12:00"}}}}
    extracted = {
        "S1": {
            "cutoff_vgm": Extracted("2026-10-05", "PLN"),
            "cutoff_document": Extracted("2026-10-06", "PLN"),
        }
    }
    assert evaluate_fields(gold, extracted).scores["cutoff"].tp == 2
    extracted["S1"]["cutoff_full"] = Extracted("2026-10-01", "PLN")
    score = evaluate_fields(gold, extracted).scores["cutoff"]
    assert (score.tp, score.fp, score.fn) == (2, 1, 0)


def test_a_field_the_system_misses_is_a_false_negative() -> None:
    gold = {"S1": {"booking": {"value": "990000101"}}, "S2": {"booking": {"value": "990000202"}}}
    score = evaluate_fields(gold, {"S1": {"booking": Extracted("990000101", None)}}).scores[
        "booking"
    ]
    assert (score.tp, score.fp, score.fn) == (1, 0, 1)


# --- verdicts ---------------------------------------------------------------------------


def test_a_gold_field_covering_several_fields_needs_all_of_them_right() -> None:
    gold = {
        "S1": {
            "cutoff": {"verdict": "NOT_IN_ERP"},
            "booking": {"verdict": "MATCH"},
            "vessel": {"verdict": "MATCH"},
            "incidents": {"value": []},
        }
    }
    verdicts = {
        "S1": [
            verdict("cutoff_vgm", VerdictCode.NOT_IN_ERP),
            verdict("cutoff_full", VerdictCode.NOT_IN_ERP),
            verdict("booking", VerdictCode.DISCREPANCY),
        ]
    }
    evaluation = evaluate_verdicts(gold, verdicts)
    assert evaluation.by_field["cutoff"].right == 1 and evaluation.by_field["booking"].right == 0
    assert evaluation.overall.total == 3
    assert {(m.field, m.got) for m in evaluation.mismatches} == {
        ("booking", "DISCREPANCY"),
        ("vessel", NO_VERDICT),
    }
    assert evaluation.overall.rate == 1 / 3


def test_verdicts_give_a_confusion_and_the_detection_of_what_needs_action() -> None:
    gold = {
        "S1": {
            "vessel": {"verdict": "ERP_ERROR"},
            "booking": {"verdict": "MATCH"},
            "stuffing": {"verdict": "DISCREPANCY"},
            "customs_release": {"verdict": "ERP_MISSING"},
        }
    }
    verdicts = {
        "S1": [
            verdict("vessel", VerdictCode.ERP_ERROR),
            verdict("booking", VerdictCode.DISCREPANCY),
            verdict("stuffing", VerdictCode.ERP_NEWER),
            verdict("customs_release", VerdictCode.DISCREPANCY),
        ]
    }
    evaluation = evaluate_verdicts(gold, verdicts)
    by_verdict = evaluation.by_verdict()
    assert (by_verdict["ERP_ERROR"].tp, by_verdict["DISCREPANCY"].fp) == (1, 2)
    assert by_verdict["DISCREPANCY"].fn == 1
    # Right action only when the verdict is exact; a false alarm on a MATCH is a false positive.
    actionable = evaluation.actionable
    assert (actionable.tp, actionable.fp, actionable.fn) == (1, 2, 2)


def test_nothing_scored_is_zero() -> None:
    assert evaluate_verdicts({}, {}).overall.rate == 0.0


# --- mails ------------------------------------------------------------------------------


def test_mails_are_paired_by_file_and_position_and_noise_by_file_order() -> None:
    gold = {
        "S1": [["BKG"], ["VSL", "BKG"]],
        "S2": [["TRP"]],
        NOISE_KEY: [["OTR"], ["OTR"]],
    }
    outcomes = [
        outcome("S1.eml", 1, (MailClass.VESSEL,), (("S1", AUTO),)),
        outcome("S1.eml", 0, (MailClass.BOOKING, MailClass.DOCUMENTATION), (("S1", AUTO),)),
        outcome("S2.eml", 0, (MailClass.TRANSPORT,), (("S1", AUTO),)),
        outcome("N1.eml", None, (MailClass.OTHER,)),
        outcome("N2.eml", None, (MailClass.OTHER,), (("S2", REVIEW),)),
    ]
    evaluation = evaluate_mails(gold, outcomes)
    assert evaluation.primary.right == 5
    assert (evaluation.by_class["BKG"].fn, evaluation.by_class["DOC"].fp) == (1, 1)
    assert evaluation.association == {"auto_right": 2, "auto_wrong": 1, "noise_right": 1,
                                      "noise_wrong": 1}  # fmt: skip
    assert evaluation.automatic_precision.rate == pytest.approx(2 / 3)
    assert evaluation.automatic_coverage.rate == pytest.approx(3 / 5)


def test_review_missing_and_unpaired_mails() -> None:
    gold = {"S1": [["BKG"], ["CUS"], ["TRP"]]}
    outcomes = [
        outcome("S1.msg", 0, (MailClass.BOOKING,), (("S1", REVIEW), ("S9", REVIEW))),
        outcome("S1.msg", 1, ()),
    ]
    evaluation = evaluate_mails(gold, outcomes)
    assert evaluation.association == {"review": 1, "missing": 2}
    assert evaluation.unpaired == 1
    assert evaluation.primary.right == 1
    assert {(m.unit, m.field) for m in evaluation.mismatches} >= {("class", "M2"), ("class", "M3")}
