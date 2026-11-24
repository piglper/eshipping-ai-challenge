from eshipping_ai.application.evaluate import NO_VERDICT, evaluate_verdicts
from eshipping_ai.domain.model import Verdict
from eshipping_ai.domain.vocabulary import VerdictCode
from tests.builders import NOW


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
    assert evaluation.right["cutoff"] == 1 and evaluation.right["booking"] == 0
    assert sum(evaluation.total.values()) == 3
    assert {(m.field, m.got) for m in evaluation.mismatches} == {
        ("booking", ("DISCREPANCY",)),
        ("vessel", (NO_VERDICT,)),
    }
    assert evaluation.accuracy == 1 / 3


def test_nothing_scored_is_zero() -> None:
    assert evaluate_verdicts({}, {}).accuracy == 0.0
