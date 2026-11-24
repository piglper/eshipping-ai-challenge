"""Deterministic extraction of equipment: number and type of containers (RF-23, A-22).

The many ways to write a container type (``40HC``, ``40'HC``, ``1x40'``, ``M40HC``,
``40 DH``) are mapped to the ISO 6346 size and type code. TEU follows from the size
(A-23): 20 feet is one TEU, 40 and 45 feet are two.
"""

import re
from dataclasses import dataclass

_TYPE_CODES: dict[tuple[int, str], str] = {
    (20, "DV"): "22G1",
    (40, "DV"): "42G1",
    (40, "HC"): "45G1",
    (45, "HC"): "L5G1",
    (20, "RF"): "22R1",
    (40, "RF"): "42R1",
    (40, "RH"): "45R1",
    (20, "OT"): "22U1",
    (40, "OT"): "42U1",
    (20, "FR"): "22P1",
    (40, "FR"): "42P1",
}
_ALIASES = {
    "": "DV",
    "DC": "DV",
    "GP": "DV",
    "ST": "DV",
    "STD": "DV",
    "HQ": "HC",
    "DH": "HC",
    "HIGH CUBE": "HC",
    "REEFER": "RF",
    "RH": "RH",
    "OPEN TOP": "OT",
    "FLAT": "FR",
}
_TYPE_WORDS = "HC|HQ|DV|DC|GP|ST|STD|DH|RF|RH|OT|FR|HIGH CUBE|REEFER|OPEN TOP|FLAT"
_EQUIPMENT_RE = re.compile(
    rf"(?:(?P<count>\d{{1,3}})\s*[x\u00d7]\s*|\b)M?(?P<size>20|40|45)\s*(?:['`\u00b4\u2019]|ft|pies)?"
    rf"\s*(?P<type>{_TYPE_WORDS})?(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_FEET_PER_TEU = 20


@dataclass(frozen=True, slots=True)
class EquipmentMention:
    """A number of containers of one type, found in a text."""

    count: int
    size: int
    iso_type: str | None
    raw: str
    start: int
    end: int

    @property
    def teu(self) -> int:
        """Twenty-foot equivalent units of the mention (A-23)."""
        return self.count * (2 if self.size > _FEET_PER_TEU else 1)


def find_equipment(text: str) -> list[EquipmentMention]:
    """Find container counts and types such as ``2 x 40HC`` or ``1x20'``.

    Args:
        text: Text to search.

    Returns:
        The mentions in order of appearance. A bare ``40HC`` counts as one container; a
        size with no type has no ISO code, because the text does not say it.
    """
    found: list[EquipmentMention] = []
    for match in _EQUIPMENT_RE.finditer(text):
        word = (match["type"] or "").upper()
        size = int(match["size"])
        explicit_count = match["count"] is not None
        if not word and not explicit_count:
            continue
        kind = _ALIASES.get(word, word)
        found.append(
            EquipmentMention(
                count=int(match["count"]) if explicit_count else 1,
                size=size,
                iso_type=_TYPE_CODES.get((size, kind)) if word or explicit_count else None,
                raw=match.group(0).strip(),
                start=match.start(),
                end=match.end(),
            )
        )
    return found
