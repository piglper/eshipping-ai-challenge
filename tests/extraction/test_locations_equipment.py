import pytest

from eshipping_ai.extraction.equipment import find_equipment
from eshipping_ai.extraction.locations import (
    ROLE_POD,
    ROLE_POL,
    find_locations,
    strip_accents,
)


def test_ports_by_name_and_code_with_roles() -> None:
    text = "Port of loading: VALENCIA (ESVLC)\nPort of discharge: NEW YORK"
    found = find_locations(text)
    assert [(m.unlocode, m.role, m.from_code) for m in found] == [
        ("ESVLC", ROLE_POL, True),
        ("USNYC", ROLE_POD, False),
    ]
    assert text[found[1].start : found[1].end] == "NEW YORK"


def test_names_are_compared_without_accents_or_case() -> None:
    assert [m.unlocode for m in find_locations("sale de Málaga hacia Hamburgo")] == [
        "ESAGP",
        "DEHAM",
    ]
    assert strip_accents("MÁLAGA") == "malaga"


def test_tagged_codes_and_unknown_names() -> None:
    found = find_locations("POL=ESVLC POD=USNYC; Cartagena y Pekín")
    assert [m.unlocode for m in found] == ["ESVLC", "USNYC"]


def test_a_name_followed_by_its_code_is_reported_once() -> None:
    assert len(find_locations("VALENCIA (ESVLC)")) == 1


def test_a_port_name_inside_a_word_is_not_a_port() -> None:
    assert find_locations("Valenciano y vigorosamente") == []


@pytest.mark.parametrize(
    ("text", "count", "size", "iso", "teu"),
    [
        ("Equipment: 1 x 40HC", 1, 40, "45G1", 2),
        ("2x20DV", 2, 20, "22G1", 2),
        ("3 x 40'HC", 3, 40, "45G1", 6),
        ("1x40\u00b4", 1, 40, "42G1", 2),
        ("M40HC", 1, 40, "45G1", 2),
        ("40 DH", 1, 40, "45G1", 2),
        ("1 x 40RH", 1, 40, "45R1", 2),
        ("2 x 20 reefer", 2, 20, "22R1", 2),
    ],
)
def test_equipment_notations(text: str, count: int, size: int, iso: str, teu: int) -> None:
    (mention,) = find_equipment(text)
    assert (mention.count, mention.size, mention.iso_type, mention.teu) == (count, size, iso, teu)


def test_a_bare_size_is_not_equipment() -> None:
    assert find_equipment("pesa 40 toneladas y mide 20 metros") == []
