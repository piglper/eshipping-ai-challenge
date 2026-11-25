"""Use case: score the system against a gold standard (F4.2, docs/07_fiabilidad.md §2).

Four units are scored, each against its own part of the gold:

- **Fields**: the current value of each field according to the mails, against the value
  the gold says the mails give. A right value is a true positive; a wrong one is both a
  false positive and a false negative; a value the gold does not expect is a false
  positive. The classifier (planned, estimated, actual) is scored on the right values.
- **Verdicts**: the verdict of each field against the ERP. Besides the exact verdict, the
  verdicts that ask for an action (ADR-0009 §6) are scored as a detection problem.
- **Classes**: the classes of each mail, primary and secondary.
- **Association**: the shipment of each mail, telling apart the automatic ones, the ones
  left for review and the noise.

Each failure is also traced to the stage that lost it (F4.3): a field that was not
extracted, extracted wrong, or extracted right but not chosen as current value; a verdict
wrong because its value was, or wrong on its own (the reconciliation). Each expected value
is counted by the tier and zone that resolved it, so that the share left to people and the
errors accepted without review are visible.

The gold may cover several system fields with one name: ``cutoff`` covers the three
cut-offs and ``equipment`` the number of containers. Fields the gold leaves out of a
shipment are not scored. Every proportion carries its 95 % Wilson interval, because the
gold is small (docs/07_fiabilidad.md §6). The report holds counts only; the list of
mismatches, which names shipments, is kept apart for local use.
"""

import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from eshipping_ai.domain.identifiers import normalize_reference
from eshipping_ai.domain.model import FieldState, Observation, Verdict
from eshipping_ai.domain.ports import (
    MailOutcome,
    ObservationStore,
    ProcessingStore,
    ProjectionStore,
)
from eshipping_ai.domain.vocabulary import AssociationStatus, VerdictCode

GOLD_TO_FIELDS: dict[str, tuple[str, ...]] = {
    "booking": ("booking",),
    "vessel": ("vessel",),
    "vessel_departure": ("vessel_departure",),
    "vessel_arrival_pod": ("vessel_arrival_pod",),
    "stuffing": ("stuffing",),
    "customs_release": ("customs_release",),
    "cutoff": ("cutoff_document", "cutoff_vgm", "cutoff_full"),
    "equipment": ("equipment_count",),
}
CUTOFF_KEYS = {"DCO": "cutoff_document", "VCO": "cutoff_vgm", "FCO": "cutoff_full"}
DATE_FIELDS = frozenset(
    {"vessel_departure", "vessel_arrival_pod", "stuffing", "customs_release", "cutoff"}
)
# Verdicts that ask an operator to act (ADR-0009 §6): complete or correct the ERP, or check.
ACTIONABLE = frozenset(
    code.value for code in (VerdictCode.ERP_ERROR, VerdictCode.DISCREPANCY, VerdictCode.ERP_MISSING)
)
NO_VERDICT = "NONE"
NOISE_KEY = "_noise"
_Z_95 = 1.96
_VESSEL_PREFIX_RE = re.compile(r"^(?:M/V|M\.V\.|MV|M/S|MS|M/T|MT)\s+", re.IGNORECASE)

# --- measures ---------------------------------------------------------------------------


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    """Return the 95 % Wilson score interval of a proportion; (0, 1) if nothing was counted."""
    if total == 0:
        return 0.0, 1.0
    rate = successes / total
    spread = _Z_95**2 / total
    centre = (rate + spread / 2) / (1 + spread)
    half = _Z_95 * math.sqrt(rate * (1 - rate) / total + spread / (4 * total)) / (1 + spread)
    return max(0.0, centre - half), min(1.0, centre + half)


@dataclass(slots=True)
class Proportion:
    """Right out of total, with its interval."""

    right: int = 0
    total: int = 0

    def add(self, *, ok: bool) -> None:
        """Count one case."""
        self.total += 1
        self.right += ok

    @property
    def rate(self) -> float:
        """Share of right cases; 0 if nothing was counted."""
        return self.right / self.total if self.total else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        """95 % Wilson interval of the rate."""
        return wilson_interval(self.right, self.total)


@dataclass(slots=True)
class Score:
    """True positives, false positives and false negatives of a detection or extraction."""

    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        """Share of what the system gave that is right; 0 if it gave nothing."""
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        """Share of what the gold expects that the system gave; 0 if it expects nothing."""
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        """Harmonic mean of precision and recall."""
        both = self.precision + self.recall
        return 2 * self.precision * self.recall / both if both else 0.0

    @property
    def precision_interval(self) -> tuple[float, float]:
        """95 % Wilson interval of the precision."""
        return wilson_interval(self.tp, self.tp + self.fp)

    @property
    def recall_interval(self) -> tuple[float, float]:
        """95 % Wilson interval of the recall."""
        return wilson_interval(self.tp, self.tp + self.fn)

    def count(self, *, expected: bool, given: bool, right: bool) -> None:
        """Count one comparison.

        Args:
            expected: The gold expects a value.
            given: The system gave one.
            right: Both agree.
        """
        if expected and given and right:
            self.tp += 1
            return
        self.fp += given
        self.fn += expected


def total_score(scores: Mapping[str, Score]) -> Score:
    """Add up several scores (micro average)."""
    return Score(
        tp=sum(s.tp for s in scores.values()),
        fp=sum(s.fp for s in scores.values()),
        fn=sum(s.fn for s in scores.values()),
    )


@dataclass(frozen=True, slots=True)
class Mismatch:
    """A gold item the system did not reproduce; it names the shipment, so it stays local."""

    unit: str
    shipment_id: str
    field: str
    expected: str
    got: str


# --- fields -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Extracted:
    """The current value of a system field, how it was obtained and what else was read.

    ``tier`` and ``zone`` are those of the observation behind the value; ``candidates`` are
    the values of every observation of the field, chosen or not.
    """

    value: str | None
    classifier: str | None
    tier: str | None = None
    zone: str | None = None
    candidates: tuple[str, ...] = ()


# Stage that lost a value of the gold (F4.3).
NOT_EXTRACTED = "not_extracted"
EXTRACTED_WRONG = "extracted_wrong"
NOT_CHOSEN = "not_chosen"
SPURIOUS = "spurious"
UNRESOLVED = "unresolved"


@dataclass(slots=True)
class FieldEvaluation:
    """Extraction scores and classifier agreement, by gold field."""

    scores: dict[str, Score] = field(default_factory=lambda: defaultdict(Score))
    classifier: dict[str, Proportion] = field(default_factory=lambda: defaultdict(Proportion))
    stages: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    resolution: Counter[tuple[str, str, bool]] = field(default_factory=Counter)
    mismatches: list[Mismatch] = field(default_factory=list)

    @property
    def automatic_precision(self) -> Proportion:
        """Right values among those accepted without review (RNF-11)."""
        accepted = {k: n for k, n in self.resolution.items() if k[1] == "auto"}
        return Proportion(
            right=sum(n for k, n in accepted.items() if k[2]), total=sum(accepted.values())
        )


def _dates(value: str) -> tuple[date, ...] | None:
    """Read a date, a date and time, or a range ``start/end``; None if it is none of them."""
    try:
        return tuple(date.fromisoformat(part.strip()[:10]) for part in value.split("/"))
    except ValueError:
        return None


def _vessel(name: str) -> str:
    return " ".join(_VESSEL_PREFIX_RE.sub("", name.strip()).upper().split())


def values_agree(gold_field: str, expected: str, got: str, tolerance_days: int = 0) -> bool:
    """Tell whether a system value is the one the gold expects.

    Bookings are compared without separators, vessels without their prefix and case, dates
    to the day (or within the tolerance of the gold) and ranges end by end.
    """
    if gold_field == "booking":
        return normalize_reference(expected) == normalize_reference(got)
    if gold_field == "vessel":
        return _vessel(expected) == _vessel(got)
    if gold_field in DATE_FIELDS:
        want, have = _dates(expected), _dates(got)
        if want is None or have is None or len(want) != len(have):
            return False
        return all(abs((a - b).days) <= tolerance_days for a, b in zip(want, have, strict=True))
    return expected.strip() == got.strip()


def _expected_values(name: str, value: object) -> list[tuple[tuple[str, ...], str | None]]:
    """Turn a gold value into (system fields that may hold it, expected value) pairs.

    A cut-off whose kind the labeller was not sure of (``FCO?``) may be held by any of the
    three cut-off fields.
    """
    if name == "cutoff":
        if not isinstance(value, Mapping):
            return []
        pairs: list[tuple[tuple[str, ...], str | None]] = []
        for key, when in value.items():
            kind = str(key).rstrip("?")
            sure = not str(key).endswith("?") and kind in CUTOFF_KEYS
            fields = (CUTOFF_KEYS[kind],) if sure else GOLD_TO_FIELDS["cutoff"]
            pairs.append((fields, None if when is None else str(when)))
        return pairs
    if value is None:
        return [(GOLD_TO_FIELDS[name], None)]
    if name == "stuffing" and isinstance(value, Mapping):
        when = value.get("date")
        return [(GOLD_TO_FIELDS[name], None if when is None else str(when))]
    if name == "equipment" and isinstance(value, Mapping):
        count = value.get("count")
        return [(GOLD_TO_FIELDS[name], None if count is None else str(count))]
    return [(GOLD_TO_FIELDS[name], str(value))]


def evaluate_fields(
    gold: Mapping[str, Mapping[str, Mapping[str, object]]],
    extracted: Mapping[str, Mapping[str, Extracted]],
    tolerance_days: Mapping[str, int] | None = None,
) -> FieldEvaluation:
    """Score the current values of the system against the values of the gold.

    Args:
        gold: Shipment to gold field to its expectation, with ``value`` and, for events,
            ``classifier``.
        extracted: Shipment to system field to its current value.
        tolerance_days: Allowed difference in days by gold field; 0 if missing.

    Returns:
        Scores and classifier agreement by gold field, and the mismatches. A system
        cut-off that no cut-off of the gold accounts for is a false positive.
    """
    tolerance = tolerance_days or {}
    evaluation = FieldEvaluation()
    for shipment_id, fields in gold.items():
        system = extracted.get(shipment_id, {})
        given = {f: e for f, e in system.items() if e.value is not None}
        for name, expectation in fields.items():
            if name not in GOLD_TO_FIELDS or "value" not in expectation:
                continue
            score = evaluation.scores[name]
            used: set[str] = set()
            for candidates, want in _expected_values(name, expectation["value"]):
                free = [f for f in candidates if f in given and f not in used]
                match = next(
                    (
                        f
                        for f in free
                        if want is not None
                        and values_agree(name, want, given[f].value or "", tolerance.get(name, 0))
                    ),
                    None,
                )
                chosen = match or (free[0] if free else None)
                if chosen:
                    used.add(chosen)
                score.count(expected=want is not None, given=chosen is not None, right=bool(match))
                if want is not None:
                    stage = _stage(name, want, candidates, system, chosen, match, tolerance)
                    evaluation.stages[name][stage] += 1
                    evaluation.resolution[_resolution(system, chosen, match)] += 1
                elif chosen is not None:
                    evaluation.stages[name][SPURIOUS] += 1
                if match and "classifier" in expectation:
                    evaluation.classifier[name].add(
                        ok=given[match].classifier == expectation["classifier"]
                    )
                elif not match and (want is not None or chosen is not None):
                    got = given[chosen].value if chosen else None
                    evaluation.mismatches.append(
                        Mismatch("field", shipment_id, name, str(want), str(got))
                    )
            if name == "cutoff":
                for extra in (f for f in GOLD_TO_FIELDS[name] if f in given and f not in used):
                    score.count(expected=False, given=True, right=False)
                    evaluation.stages[name][SPURIOUS] += 1
                    evaluation.mismatches.append(
                        Mismatch("field", shipment_id, extra, "None", str(given[extra].value))
                    )
    return evaluation


def _stage(  # noqa: PLR0913, PLR0917 - one comparison and everything known about it
    name: str,
    want: str,
    candidates: tuple[str, ...],
    system: Mapping[str, Extracted],
    chosen: str | None,
    match: str | None,
    tolerance: Mapping[str, int],
) -> str:
    """Tell where an expected value was lost, or ``right`` if it was not."""
    if match:
        return "right"
    read = [v for f in candidates for v in system.get(f, _NOTHING).candidates]
    if not read:
        return NOT_EXTRACTED
    if any(values_agree(name, want, value, tolerance.get(name, 0)) for value in read):
        return NOT_CHOSEN
    return EXTRACTED_WRONG


def _resolution(
    system: Mapping[str, Extracted], chosen: str | None, match: str | None
) -> tuple[str, str, bool]:
    """Tier, zone and correctness of the value given for an expected one."""
    if chosen is None:
        return (UNRESOLVED, UNRESOLVED, False)
    value = system[chosen]
    return (value.tier or UNRESOLVED, value.zone or UNRESOLVED, match is not None)


_NOTHING = Extracted(None, None)


# --- verdicts ---------------------------------------------------------------------------


@dataclass(slots=True)
class VerdictEvaluation:
    """Agreement with the verdicts of the gold, by field and by verdict."""

    by_field: dict[str, Proportion] = field(default_factory=lambda: defaultdict(Proportion))
    confusion: Counter[tuple[str, str]] = field(default_factory=Counter)
    actionable: Score = field(default_factory=Score)
    mismatches: list[Mismatch] = field(default_factory=list)
    causes: Counter[str] = field(default_factory=Counter)
    reconciliation_errors: Counter[tuple[str, str]] = field(default_factory=Counter)

    def attribute(self, field_mismatches: Sequence[Mismatch]) -> None:
        """Split the wrong verdicts between a wrong value and the reconciliation itself.

        Args:
            field_mismatches: The values the extraction got wrong, by shipment and field.
        """
        wrong_values = {(m.shipment_id, m.field) for m in field_mismatches}
        wrong_values |= {(m.shipment_id, "cutoff") for m in field_mismatches if "cutoff" in m.field}
        for miss in self.mismatches:
            if (miss.shipment_id, miss.field) in wrong_values:
                self.causes["value"] += 1
            else:
                self.causes["reconciliation"] += 1
                self.reconciliation_errors[miss.expected, miss.got] += 1

    @property
    def overall(self) -> Proportion:
        """Exact verdict over every scored field."""
        return Proportion(
            right=sum(p.right for p in self.by_field.values()),
            total=sum(p.total for p in self.by_field.values()),
        )

    def by_verdict(self) -> dict[str, Score]:
        """Precision and recall of each verdict, from the confusion counts."""
        scores: dict[str, Score] = defaultdict(Score)
        for (expected, got), n in self.confusion.items():
            if expected == got:
                scores[expected].tp += n
            else:
                scores[expected].fn += n
                scores[got].fp += n
        return dict(sorted(scores.items()))


def evaluate_verdicts(
    gold: Mapping[str, Mapping[str, Mapping[str, object]]],
    verdicts: Mapping[str, Sequence[Verdict]],
) -> VerdictEvaluation:
    """Score the verdicts of the system against the gold.

    Args:
        gold: Shipment to gold field to its expectation, with a ``verdict`` key.
        verdicts: Shipment to its current verdicts.

    Returns:
        Exact agreement by field, the confusion counts and the detection of the verdicts
        that ask for an action. A gold field covering several fields counts the verdict of
        the fields that have one: the gold of a cut-off lists only the cut-offs the mails
        give, so the others have no verdict to match; differing verdicts are joined by ``+``.
    """
    evaluation = VerdictEvaluation()
    for shipment_id, fields in gold.items():
        got_by_field = {v.field: v.code.value for v in verdicts.get(shipment_id, ())}
        for name, expectation in fields.items():
            covered = GOLD_TO_FIELDS.get(name)
            if covered is None or "verdict" not in expectation:
                continue
            expected = str(expectation["verdict"])
            codes = sorted({got_by_field[f] for f in covered if f in got_by_field})
            got = "+".join(codes) or NO_VERDICT
            evaluation.by_field[name].add(ok=got == expected)
            evaluation.confusion[expected, got] += 1
            evaluation.actionable.count(
                expected=expected in ACTIONABLE,
                given=any(code in ACTIONABLE for code in codes),
                right=expected in ACTIONABLE and got == expected,
            )
            if got != expected:
                evaluation.mismatches.append(Mismatch("verdict", shipment_id, name, expected, got))
    return evaluation


# --- mails: classes and association -----------------------------------------------------


@dataclass(slots=True)
class MailEvaluation:
    """Classes and association of the mails of the gold."""

    primary: Proportion = field(default_factory=Proportion)
    primary_confusion: Counter[tuple[str, str]] = field(default_factory=Counter)
    by_class: dict[str, Score] = field(default_factory=lambda: defaultdict(Score))
    association: Counter[str] = field(default_factory=Counter)
    unpaired: int = 0
    mismatches: list[Mismatch] = field(default_factory=list)

    @property
    def automatic_precision(self) -> Proportion:
        """Right shipment among the mails the system associated on its own (RNF-10)."""
        right = self.association["auto_right"]
        return Proportion(right=right, total=right + self.association["auto_wrong"])

    @property
    def automatic_coverage(self) -> Proportion:
        """Mails associated right on their own (or left as noise right), out of all."""
        return Proportion(
            right=self.association["auto_right"] + self.association["noise_right"],
            total=sum(self.association.values()),
        )


def _association_outcome(expected: str | None, outcome: MailOutcome | None) -> str:
    shipments = outcome.shipments if outcome else ()
    auto = {s for s, status in shipments if status is AssociationStatus.AUTO}
    review = {s for s, status in shipments if status is not AssociationStatus.AUTO}
    if expected is None:
        return "noise_right" if not shipments else "noise_wrong"
    if auto:
        return "auto_right" if auto == {expected} else "auto_wrong"
    if expected in review:
        return "review"
    return "missing"


def pair_mails(
    gold_mails: Mapping[str, Sequence[Sequence[str]]], outcomes: Sequence[MailOutcome]
) -> list[tuple[str, int, Sequence[str], MailOutcome | None]]:
    """Pair each mail of the gold with what the system made of it.

    The gold lists, for each shipment, the classes of the mails embedded in the file named
    after that shipment, in the order they are embedded (``M1``, ``M2``...). Mails of files
    named after no shipment are paired, in file order, with the noise of the gold.

    Returns:
        (shipment or noise key, position, gold classes, system outcome or None) tuples.
    """
    shipments = [key for key in gold_mails if key != NOISE_KEY]
    by_file: dict[str, dict[int, MailOutcome]] = defaultdict(dict)
    for outcome in outcomes:
        by_file[outcome.source_ref or ""][outcome.position or 0] = outcome
    pairs: list[tuple[str, int, Sequence[str], MailOutcome | None]] = []
    owners: dict[str, str] = {}
    for source in by_file:
        owner = next((key for key in shipments if key in source), None)
        if owner is not None:
            owners[owner] = source
    for key in shipments:
        found = by_file.get(owners.get(key, "\0"), {})
        pairs.extend(
            (key, position, classes, found.get(position))
            for position, classes in enumerate(gold_mails[key])
        )
    noise = [
        outcome
        for source in sorted(by_file)
        if source not in owners.values()
        for _, outcome in sorted(by_file[source].items())
    ]
    for position, classes in enumerate(gold_mails.get(NOISE_KEY, ())):
        pairs.append(
            (NOISE_KEY, position, classes, noise[position] if position < len(noise) else None)
        )
    return pairs


def evaluate_mails(
    gold_mails: Mapping[str, Sequence[Sequence[str]]], outcomes: Sequence[MailOutcome]
) -> MailEvaluation:
    """Score the classes and the association of the mails against the gold.

    Args:
        gold_mails: Shipment (or the noise key) to the classes of each of its mails,
            primary first.
        outcomes: What the processing made of each mail.

    Returns:
        Primary class accuracy, scores by class (every class of a mail counts) and the
        association outcomes: ``auto_right``, ``auto_wrong``, ``review``, ``missing``,
        ``noise_right`` and ``noise_wrong``.
    """
    evaluation = MailEvaluation()
    for key, position, classes, outcome in pair_mails(gold_mails, outcomes):
        label = f"M{position + 1}"
        if outcome is None:
            evaluation.unpaired += 1
        got = [c.value for c in outcome.classes] if outcome else []
        primary_ok = bool(got) and bool(classes) and got[0] == classes[0]
        evaluation.primary.add(ok=primary_ok)
        if not primary_ok:
            want, have = (classes[0] if classes else "-"), (got[0] if got else "-")
            evaluation.primary_confusion[want, have] += 1
            evaluation.mismatches.append(Mismatch("class", key, label, want, have))
        for name in set(classes) | set(got):
            evaluation.by_class[name].count(
                expected=name in classes, given=name in got, right=name in classes and name in got
            )
        expected = None if key == NOISE_KEY else key
        outcome_name = _association_outcome(expected, outcome)
        evaluation.association[outcome_name] += 1
        if outcome_name not in {"auto_right", "noise_right"}:
            shipments = ",".join(s for s, _ in outcome.shipments) if outcome else "-"
            evaluation.mismatches.append(
                Mismatch("association", key, label, str(expected), shipments or "-")
            )
    evaluation.by_class = dict(sorted(evaluation.by_class.items()))
    return evaluation


# --- the whole evaluation ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Every score of one run against one gold standard."""

    gold_version: str
    gold_review: str
    shipments: int
    fields: FieldEvaluation
    verdicts: VerdictEvaluation
    mails: MailEvaluation

    @property
    def mismatches(self) -> list[Mismatch]:
        """Every mismatch; they name shipments, so they are for local use only."""
        return [*self.mails.mismatches, *self.fields.mismatches, *self.verdicts.mismatches]


def _extracted(
    states: Sequence[FieldState], observations: Sequence[Observation]
) -> dict[str, Extracted]:
    by_id = {o.observation_id: o for o in observations}
    read: dict[str, list[str]] = defaultdict(list)
    for item in observations:
        read[item.field].append(item.value)
    result = {}
    for state in states:
        winner = by_id.get(state.winning_observation_id or "")
        result[state.field] = Extracted(
            value=state.value,
            classifier=winner.classifier.value if winner else None,
            tier=winner.provenance.tier.value if winner else None,
            zone=winner.zone.value if winner else None,
            candidates=tuple(read.get(state.field, ())),
        )
    for name, values in read.items():
        result.setdefault(name, Extracted(None, None, candidates=tuple(values)))
    return result


class EvaluateRun:
    """Score what is stored for a run against a gold standard."""

    def __init__(
        self,
        projections: ProjectionStore,
        observations: ObservationStore,
        processing: ProcessingStore,
    ) -> None:
        """Wire the stores the evaluation reads."""
        self._projections = projections
        self._observations = observations
        self._processing = processing

    def run(self, gold: Mapping[str, object]) -> EvaluationReport:
        """Score the stored run against a gold standard in the format of docs/01 §6.

        Args:
            gold: The gold standard, with ``meta``, ``mails`` and ``expedientes``.

        Returns:
            The report with every score.
        """
        meta = _mapping(gold.get("meta"))
        shipments = {str(k): _mapping(v) for k, v in _mapping(gold.get("expedientes")).items()}
        expectations = {
            s: {str(name): _mapping(e) for name, e in fields.items()}
            for s, fields in shipments.items()
        }
        extracted = {
            s: _extracted(
                self._projections.field_states_for(s), self._observations.observations_for(s)
            )
            for s in expectations
        }
        verdicts = {s: self._projections.verdicts_for(s) for s in expectations}
        tolerance = {
            str(k): int(str(v)) for k, v in _mapping(meta.get("date_tolerance_days")).items()
        }
        gold_mails = {
            str(k): [[str(c) for c in classes] for classes in v]
            for k, v in _mapping(gold.get("mails")).items()
            if isinstance(v, list)
        }
        fields = evaluate_fields(expectations, extracted, tolerance)
        verdict_evaluation = evaluate_verdicts(expectations, verdicts)
        verdict_evaluation.attribute(fields.mismatches)
        return EvaluationReport(
            gold_version=str(meta.get("version", "")),
            gold_review=str(meta.get("review", "")),
            shipments=len(expectations),
            fields=fields,
            verdicts=verdict_evaluation,
            mails=evaluate_mails(gold_mails, self._processing.mail_outcomes()),
        )


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}
