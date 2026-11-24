import csv
import email
import json
from email import policy
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from eshipping_ai.domain.identifiers import is_valid_container_number
from eshipping_ai.domain.vocabulary import VerdictCode
from eshipping_ai.synthetic.__main__ import main
from eshipping_ai.synthetic.build import NOISE_KEY, build
from eshipping_ai.synthetic.spec import Spec, load_spec

SPEC_PATH = Path(__file__).parents[2] / "data_sample" / "spec" / "sample.yaml"


@pytest.fixture(scope="module")
def spec() -> Spec:
    return load_spec(SPEC_PATH)


@pytest.fixture
def built(spec: Spec, tmp_path: Path) -> Path:
    build(spec, tmp_path)
    return tmp_path


def parse(path: Path) -> EmailMessage:
    message = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    assert isinstance(message, EmailMessage)
    return message


def embedded(container: EmailMessage) -> list[EmailMessage]:
    parts = []
    for part in container.iter_attachments():
        assert part.get_content_type() == "message/rfc822"
        inner = part.get_content()
        assert isinstance(inner, EmailMessage)
        parts.append(inner)
    return parts


def test_one_container_per_shipment_with_embedded_mails(spec: Spec, built: Path) -> None:
    for shipment in spec.shipments:
        container = parse(built / "mails" / f"{shipment.operation}.eml")
        inner = embedded(container)
        assert [m["Subject"] for m in inner] == [m.subject for m in shipment.mails]
        assert all(m["Date"] and m["From"] and m["Message-ID"] for m in inner)


def test_forward_quotes_the_original(built: Path) -> None:
    inner = embedded(parse(built / "mails" / "ES26900002.eml"))
    body = inner[2].get_body(preferencelist=("plain",))
    assert body is not None
    text = body.get_content()
    assert "Asunto: ROLLOVER NOTICE - BKG 990000202" in text
    assert "New vessel / voyage: CELESTE FICTICIA / 013W" in text


def test_noise_is_a_standalone_mail(built: Path) -> None:
    noise = parse(built / "mails" / "N1.eml")
    assert not noise.is_multipart()


def test_erp_export_has_the_real_format(spec: Spec, built: Path) -> None:
    raw = (built / "erp.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(raw.decode("utf-8-sig").splitlines(), delimiter=";"))
    assert rows[0][0] == "Operación"
    assert len(rows) == 1 + len(spec.shipments)
    assert rows[1][rows[0].index("Booking")] == "990000101 "  # trailing space kept on purpose


def test_gold_covers_every_verdict_and_mail(spec: Spec, built: Path) -> None:
    gold: dict[str, Any] = json.loads((built / "gold.json").read_text(encoding="utf-8"))
    assert set(gold) == {"meta", "mails", "expedientes"}
    verdicts = {
        field["verdict"] for fields in gold["expedientes"].values() for field in fields.values()
    }
    assert verdicts == {code.value for code in VerdictCode}
    assert gold["mails"][NOISE_KEY] == [["OTR"]]
    assert len(gold["mails"]) == len(spec.shipments) + 1


def test_synthetic_containers_are_valid(spec: Spec) -> None:
    for shipment in spec.shipments:
        equipment = shipment.gold.get("equipment")
        assert equipment is not None
        assert isinstance(equipment.value, dict)
        for number in equipment.value["containers"]:
            assert is_valid_container_number(number)


def test_build_is_deterministic(spec: Spec, tmp_path: Path) -> None:
    first, second = build(spec, tmp_path / "a"), build(spec, tmp_path / "b")
    for one, other in zip(
        (*first.mail_files, first.erp_file, first.gold_file),
        (*second.mail_files, second.erp_file, second.gold_file),
        strict=True,
    ):
        assert one.read_bytes() == other.read_bytes()


def test_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--spec", str(SPEC_PATH), "--out", str(tmp_path)])
    assert "5 correos" in capsys.readouterr().out
    assert (tmp_path / "gold.json").exists()


def raw_spec() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["shipments"][0]["mails"][0].update({"from": "nobody"}), "unknown party"),
        (lambda d: d["shipments"][0]["mails"][0].update({"quote": "M2"}), "not an earlier"),
        (lambda d: d["shipments"][0]["gold"]["booking"].update({"source": "M9"}), "unknown source"),
        (lambda d: d["shipments"][1]["erp"].pop("Master"), "ERP columns"),
        (lambda d: d["shipments"][0]["mails"].append(d["shipments"][0]["mails"][0]), "repeated"),
        (lambda d: d["shipments"][0]["gold"]["booking"].update({"verdict": "OK"}), "verdict"),
    ],
)
def test_invalid_specs_are_rejected(mutate: Any, message: str) -> None:
    data = raw_spec()
    mutate(data)
    with pytest.raises(ValidationError, match=message):
        Spec.model_validate(data)
