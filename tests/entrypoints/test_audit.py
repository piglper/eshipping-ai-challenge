from email.message import EmailMessage
from pathlib import Path

from eshipping_ai.entrypoints.audit import Hit, collect_secrets, is_specific, scan


def _data(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    (data / "mails").mkdir(parents=True)
    (data / "erp.csv").write_bytes(
        "Operación;Booking;Cliente Op.;SWB / OBL Evento;Cont\n"
        "ES26999999;881234567;CITRICOS INVENTADOS S.L.;Completado;SYNU9999990\n".encode("utf-8-sig")
    )
    mail = EmailMessage()
    mail["From"] = "Ana <ana@cliente-inventado.example>"
    mail["To"] = "ops@gmail.com"
    mail["Subject"] = "Contenedor SYNU8888881"
    mail.set_content("Hola")
    (data / "mails" / "m.eml").write_bytes(bytes(mail))
    return data


def test_the_real_values_are_collected_by_category(tmp_path: Path) -> None:
    secrets = collect_secrets(_data(tmp_path))
    assert secrets["expediente"] == {"ES26999999"}
    assert secrets["booking"] == {"881234567"}
    assert secrets["cliente"] == {"CITRICOS INVENTADOS S.L."}
    assert secrets["contenedor"] == {"SYNU9999990", "SYNU8888881"}
    assert secrets["correo"] == {"ana@cliente-inventado.example", "ops@gmail.com"}
    assert secrets["dominio"] == {"cliente-inventado.example"}  # public mail domains are not
    assert "bl" not in secrets  # a document state is vocabulary, not data


def test_generic_words_and_short_values_are_not_searched() -> None:
    assert not is_specific("Completado")
    assert not is_specific("S.L.U.")
    assert not is_specific("ABC")
    assert is_specific("881234567")


def test_a_hit_says_where_but_not_what() -> None:
    texts = {"tests/a.py": "x = 1\nassert parse('Reserva 881234567')\n", "b.md": "nada"}
    hits = scan(texts, {"booking": {"881234567"}})
    assert hits == [Hit("booking", "tests/a.py:2")]
    assert "881234567" not in repr(hits)


def test_a_value_inside_a_longer_number_is_not_a_hit() -> None:
    assert scan({"a": "ref 98812345678"}, {"booking": {"881234567"}}) == []
