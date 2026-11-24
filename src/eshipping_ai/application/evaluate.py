"""Use case: compare the verdicts with a gold standard (RNF-01; F4 widens it).

The gold gives the expected verdict of each field of each shipment. One gold field may
cover several fields of the system: ``cutoff`` covers the three cut-offs and ``equipment``
the number of containers. A gold field is right when every system field it covers has the
expected verdict; fields the gold leaves out of that list are not scored.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from eshipping_ai.domain.model import Verdict

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
NO_VERDICT = "NONE"


@dataclass(frozen=True, slots=True)
class Mismatch:
    """A gold field whose verdict the system did not reproduce."""

    shipment_id: str
    field: str
    expected: str
    got: tuple[str, ...]


@dataclass(slots=True)
class Evaluation:
    """Agreement with the gold, by field."""

    right: Counter[str] = field(default_factory=Counter)
    total: Counter[str] = field(default_factory=Counter)
    mismatches: list[Mismatch] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        """Share of gold fields with the expected verdict; 0 if nothing was scored."""
        scored = sum(self.total.values())
        return sum(self.right.values()) / scored if scored else 0.0


def evaluate_verdicts(
    gold: Mapping[str, Mapping[str, Mapping[str, object]]],
    verdicts: Mapping[str, Sequence[Verdict]],
) -> Evaluation:
    """Score the verdicts of the system against the gold.

    Args:
        gold: Shipment to gold field to its expectation, with a ``verdict`` key.
        verdicts: Shipment to its current verdicts.

    Returns:
        Right and total by gold field, and the mismatches. A gold field covering several
        fields counts the verdict of the fields that have one: the gold of a cut-off lists
        only the cut-offs the mails give, so the others have no verdict to match.
    """
    evaluation = Evaluation()
    for shipment_id, fields in gold.items():
        got = {v.field: v.code.value for v in verdicts.get(shipment_id, ())}
        for name, expected in fields.items():
            covered = GOLD_TO_FIELDS.get(name)
            if covered is None or "verdict" not in expected:
                continue
            codes = tuple(sorted({got[f] for f in covered if f in got})) or (NO_VERDICT,)
            evaluation.total[name] += 1
            if codes == (str(expected["verdict"]),):
                evaluation.right[name] += 1
            else:
                evaluation.mismatches.append(
                    Mismatch(shipment_id, name, str(expected["verdict"]), codes)
                )
    return evaluation
