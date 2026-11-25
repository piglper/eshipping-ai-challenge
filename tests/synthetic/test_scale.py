import re
from pathlib import Path

import pytest

from eshipping_ai.domain.identifiers import is_valid_container_number
from eshipping_ai.synthetic.build import build
from eshipping_ai.synthetic.scale import replicate
from eshipping_ai.synthetic.spec import load_spec

SPEC = load_spec(Path(__file__).parents[2] / "data_sample" / "spec" / "sample.yaml")


def test_the_first_copy_is_the_base_specification_renumbered() -> None:
    spec = replicate(SPEC, 1)
    for base, copy in zip(SPEC.shipments, spec.shipments, strict=True):
        assert [(m.id, m.sender, m.date, m.classes) for m in copy.mails] == [
            (m.id, m.sender, m.date, m.classes) for m in base.mails
        ]
        assert copy.gold.keys() == base.gold.keys()
    assert spec.noise == SPEC.noise


def test_every_copy_is_a_different_shipment_with_valid_identifiers() -> None:
    spec = replicate(SPEC, 3)
    assert len(spec.shipments) == 3 * len(SPEC.shipments)
    assert len(spec.noise) == 3 * len(SPEC.noise)
    operations = [s.operation for s in spec.shipments]
    assert len(set(operations)) == len(operations)
    text = spec.model_dump_json()
    containers = set(re.findall(r"SYNU\d{7}", text))
    assert len(containers) == 3 * len(set(re.findall(r"SYNU\d{7}", SPEC.model_dump_json())))
    assert all(is_valid_container_number(c) for c in containers)
    bookings = set(re.findall(r"\b9\d{8}\b", text))
    assert len(bookings) == 3 * len(set(re.findall(r"\b9\d{8}\b", SPEC.model_dump_json())))


def test_a_copy_keeps_its_own_references_consistent() -> None:
    first, copy = SPEC.shipments[0], replicate(SPEC, 2).shipments[len(SPEC.shipments)]
    assert copy.operation != first.operation
    assert copy.erp["Operación"] == copy.operation
    assert [m.id for m in copy.mails] == [m.id for m in first.mails]
    assert first.operation not in copy.model_dump_json()


def test_the_mails_of_a_later_copy_are_signed_so_none_is_a_duplicate() -> None:
    spec = replicate(SPEC, 28)
    bodies = [m.body for s in spec.shipments for m in s.mails] + [m.body for m in spec.noise]
    assert len(set(bodies)) == len(bodies)
    assert spec.shipments[-1].mails[0].body.rstrip().endswith("Equipo BB")
    assert not re.search(r"Equipo \S*\d", " ".join(bodies))


def test_the_replicated_set_builds(tmp_path: Path) -> None:
    result = build(replicate(SPEC, 2), tmp_path)
    assert len(result.mail_files) == 2 * (len(SPEC.shipments) + len(SPEC.noise))


@pytest.mark.parametrize("copies", [0, 100_000])
def test_the_number_of_copies_is_bounded(copies: int) -> None:
    with pytest.raises(ValueError, match="copies"):
        replicate(SPEC, copies)
