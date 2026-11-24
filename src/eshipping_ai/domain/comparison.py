"""Discrepancy policy, part 2: comparison with the ERP, verdicts and priorities (ADR-0009 §4-§6).

The comparison is deterministic and never uses a language model (RF-51). Each verdict
records the rule that produced it, the values compared and the ERP read it used, so that
any verdict can be explained afterwards (RNF-43). The ERP is never written to (RF-55).
"""

import hashlib
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

from eshipping_ai.domain.identifiers import normalize_reference
from eshipping_ai.domain.model import ErpRecord, ErpRecordRef, FieldState, Observation, Verdict
from eshipping_ai.domain.policy import FieldRule, ReconciliationConfig
from eshipping_ai.domain.vocabulary import (
    EventClassifier,
    EventType,
    Priority,
    SourceRank,
    SourceRole,
    TimePrecision,
    VerdictCode,
)

_VESSEL_PREFIX = ("M/V", "MV", "M.V.", "MS", "M/S", "MT", "M/T")
_URGENT_EVENTS = frozenset({EventType.ROLLED, EventType.VESSEL_CHANGE})
_PRIORITISED = frozenset({VerdictCode.ERP_ERROR, VerdictCode.DISCREPANCY, VerdictCode.ERP_MISSING})
_ADJACENT_DIGITS = 2


@dataclass(frozen=True, slots=True)
class ComparisonInput:
    """Everything needed to compare one field of one shipment with one ERP read.

    ``history`` holds the earlier values of the field, which are aliases of the current one
    (a booking replaced by a rollover, A-20). ``last_mail_known_at`` is the date of the last
    message of the shipment, used by the "ERP is newer" rule. ``issues`` maps fields to the
    coherence rule that the ERP row violates (ADR-0009 §5).
    """

    shipment_id: str
    field: str
    rule: FieldRule
    config: ReconciliationConfig
    state: FieldState
    winner: Observation | None
    history: Collection[str]
    erp: ErpRecord
    erp_read_at: datetime
    last_mail_known_at: datetime | None
    issues: dict[str, str]
    now: datetime


# --- coherence of the ERP row (ADR-0009 §5) -----------------------------------------------


def _iso(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def erp_quality_issues(record: ErpRecord) -> dict[str, str]:
    """Find the internal inconsistencies of an ERP row, without any mail.

    Args:
        record: The ERP row, with normalised fields.

    Returns:
        The field that is wrong, by the rule it breaks. When two dates cannot both be right
        the later or earlier one is blamed according to which is the usual error.
    """
    values = record.normalized
    departure = _iso(values.get("vessel_departure"))
    arrival = _iso(values.get("vessel_arrival_pod"))
    stuffing = _iso(values.get("stuffing"))
    customs = _iso(values.get("customs_release"))
    issues: dict[str, str] = {}
    if departure and arrival and departure > arrival:
        issues["vessel_arrival_pod"] = "departure_after_arrival"
    if departure and stuffing and stuffing > departure:
        issues["vessel_departure"] = "stuffing_after_departure"
    if departure and customs and customs > departure:
        issues["customs_release"] = "release_after_departure"
    return issues


# --- matching -----------------------------------------------------------------------------


def _normalise_vessel(name: str) -> str:
    upper = name.upper().strip()
    for prefix in _VESSEL_PREFIX:
        if upper.startswith(prefix + " "):
            upper = upper[len(prefix) :].strip()
    return " ".join(upper.split())


def _winner_date(winner: Observation) -> date | None:
    if winner.event_time is not None:
        return winner.event_time.date()
    return _iso(winner.value[:10])


def _dates_match(winner: Observation, erp_date: date, config: ReconciliationConfig) -> bool:
    start = _winner_date(winner)
    if start is None:
        return False
    if winner.time_precision is TimePrecision.RANGE and winner.event_time_end is not None:
        return start <= erp_date <= winner.event_time_end.date()
    if winner.time_precision is TimePrecision.APPROX:
        return abs((erp_date - start).days) <= config.approx_days
    return start == erp_date


def _values_match(ctx: ComparisonInput, winner: Observation, erp_value: str) -> bool:
    kind = ctx.rule.kind
    if kind == "date":
        erp_date = _iso(erp_value)
        return erp_date is not None and _dates_match(winner, erp_date, ctx.config)
    if kind == "text":
        ratio = SequenceMatcher(
            None, _normalise_vessel(winner.value), _normalise_vessel(erp_value)
        ).ratio()
        return ratio >= ctx.config.vessel_similarity
    wanted = normalize_reference(erp_value)
    known = {normalize_reference(winner.value), *map(normalize_reference, ctx.history)}
    return wanted in known


def _is_typo(mail_date: date, erp_date: date) -> bool:
    """Day and month swapped, or two adjacent digits transposed (typical typing errors)."""
    if mail_date.day == erp_date.month and mail_date.month == erp_date.day:
        return mail_date != erp_date
    left, right = mail_date.isoformat(), erp_date.isoformat()
    differing = [i for i, (a, b) in enumerate(zip(left, right, strict=True)) if a != b]
    return (
        len(differing) == _ADJACENT_DIGITS
        and differing[1] - differing[0] == 1
        and left[differing[0]] == right[differing[1]]
        and left[differing[1]] == right[differing[0]]
    )


# --- rules A and B (ADR-0009 §4) -----------------------------------------------------------


def _erp_is_newer(ctx: ComparisonInput, winner: Observation, erp_value: str) -> bool:
    """Rule A: the ERP probably reflects information later than the mails."""
    updated = ctx.erp.field_updated_at.get(ctx.rule.erp_key or "")
    if updated is not None:
        return updated > winner.known_at
    erp_date = _iso(erp_value)
    flagged_actual = ctx.erp.normalized.get(ctx.rule.erp_actual_key or "") == "true"
    return (
        flagged_actual
        and winner.classifier is not EventClassifier.ACTUAL
        and erp_date is not None
        and ctx.last_mail_known_at is not None
        and erp_date > ctx.last_mail_known_at.date()
    )


def _erp_is_clearly_wrong(ctx: ComparisonInput, winner: Observation, erp_value: str) -> bool:
    """Rule B: the mails have authority and the ERP value is clearly an error."""
    authoritative = (
        winner.source_rank is SourceRank.A or winner.source_role is SourceRole.HUMAN_REVIEW
    )
    if not authoritative or winner.confidence < ctx.rule.min_confidence:
        return False
    if ctx.field in ctx.issues:
        return True
    updated = ctx.erp.field_updated_at.get(ctx.rule.erp_key or "")
    if updated is not None and updated < winner.known_at:
        return True
    mail_date, erp_date = _winner_date(winner), _iso(erp_value)
    return (
        ctx.rule.kind == "date"
        and mail_date is not None
        and erp_date is not None
        and winner.classifier is EventClassifier.ACTUAL
        and _is_typo(mail_date, erp_date)
    )


# --- priority (ADR-0009 §6) ----------------------------------------------------------------


def _priority(
    ctx: ComparisonInput, winner: Observation | None, code: VerdictCode
) -> Priority | None:
    if code not in _PRIORITISED:
        return None
    if (
        winner is not None
        and winner.event_type in _URGENT_EVENTS
        and code is not VerdictCode.ERP_MISSING
    ):
        return Priority.P1
    if not ctx.rule.critical:
        return Priority.P3
    event_at = winner.event_time if winner is not None else None
    if event_at is not None and code is not VerdictCode.ERP_MISSING:
        hours = (event_at - ctx.now).total_seconds() / 3600
        if 0 <= hours <= ctx.config.urgent_horizon_hours:
            return Priority.P1
    return Priority.P2


# --- the comparison -----------------------------------------------------------------------


def _verdict(
    ctx: ComparisonInput,
    code: VerdictCode,
    rule: str,
    mail_value: str | None,
    erp_value: str | None,
) -> Verdict:
    snapshot = ctx.erp.snapshot_id
    digest = hashlib.sha256(
        "\x1f".join(
            (
                ctx.shipment_id,
                ctx.field,
                ctx.config.version,
                snapshot,
                str(mail_value),
                str(erp_value),
            )
        ).encode()
    ).hexdigest()
    return Verdict(
        verdict_id=f"vrd-{digest[:16]}",
        shipment_id=ctx.shipment_id,
        field=ctx.field,
        code=code,
        mail_value=mail_value,
        erp_value=erp_value,
        erp_record=ErpRecordRef(snapshot_id=snapshot, operation=ctx.erp.operation),
        rule=rule,
        priority=None,
        computed_at=ctx.now,
        config_version=ctx.config.version,
    )


def _with_priority(ctx: ComparisonInput, verdict: Verdict) -> Verdict:
    priority = _priority(ctx, ctx.winner, verdict.code)
    return verdict.model_copy(update={"priority": priority})


def _is_stale(ctx: ComparisonInput) -> bool:
    return ctx.now - ctx.erp_read_at > timedelta(hours=ctx.config.erp_stale_after_hours)


def _erp_empty(ctx: ComparisonInput, winner: Observation) -> Verdict:
    """The mails have a value and the ERP has none: propose to complete it, unless stale."""
    if _is_stale(ctx):
        verdict = _verdict(ctx, VerdictCode.DISCREPANCY, "stale_erp_read", winner.value, None)
    else:
        verdict = _verdict(ctx, VerdictCode.ERP_MISSING, "erp_empty", winner.value, None)
    return _with_priority(ctx, verdict)


def _both_present(ctx: ComparisonInput, winner: Observation, erp_value: str) -> Verdict:
    """Both sides have a value: match, newer ERP, clear ERP error or unattributable."""
    if _values_match(ctx, winner, erp_value):
        return _verdict(ctx, VerdictCode.MATCH, "within_tolerance", winner.value, erp_value)
    if _erp_is_newer(ctx, winner, erp_value):
        return _verdict(ctx, VerdictCode.ERP_NEWER, "rule_a_erp_newer", winner.value, erp_value)
    if _is_stale(ctx):
        code, rule = VerdictCode.DISCREPANCY, "stale_erp_read"
    elif _erp_is_clearly_wrong(ctx, winner, erp_value):
        code, rule = VerdictCode.ERP_ERROR, "rule_b_clear_error"
    else:
        code, rule = VerdictCode.DISCREPANCY, "unattributable"
    return _with_priority(ctx, _verdict(ctx, code, rule, winner.value, erp_value))


def compare_field(ctx: ComparisonInput) -> Verdict | None:
    """Compare the current value of a field with the ERP and say what it means.

    Args:
        ctx: The field, its current value, the ERP row and the policy.

    Returns:
        The verdict, or None when there is nothing to say: both sides are empty, or the
        field is in conflict (it is not compared until a person resolves it, ADR-0009 §3).
    """
    if ctx.state.in_conflict:
        return None
    erp_value = ctx.erp.normalized.get(ctx.rule.erp_key) if ctx.rule.erp_key else None
    winner = ctx.winner
    if winner is None:
        if erp_value is None:
            return None
        return _verdict(ctx, VerdictCode.MAIL_MISSING, "erp_only", None, erp_value)
    if ctx.rule.erp_key is None:
        return _verdict(ctx, VerdictCode.NOT_IN_ERP, "no_erp_column", winner.value, None)
    if erp_value is None:
        return _erp_empty(ctx, winner)
    return _both_present(ctx, winner, erp_value)
