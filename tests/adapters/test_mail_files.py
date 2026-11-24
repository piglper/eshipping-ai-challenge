from datetime import UTC, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from eshipping_ai.adapters.mail_files import (
    FolderMailSource,
    MailFileParser,
    parse_eml,
    parse_msg,
)

MADRID_SUMMER = timezone(timedelta(hours=2))


def simple_eml(*, with_html: bool = False, date: datetime | None = None) -> EmailMessage:
    message = EmailMessage()
    message["From"] = "Ana Ejemplo <ana@empresa.example>"
    message["To"] = "ops@eshipping-sintetico.example, otra@eshipping-sintetico.example"
    message["Subject"] = "BOOKING 990000101"
    message["Message-ID"] = "<id-1@empresa.example>"
    message["Date"] = format_datetime(date or datetime(2026, 9, 20, 10, 15, tzinfo=MADRID_SUMMER))
    message.set_content("ETD 08/10/2026")
    if with_html:
        message.add_alternative("<p>ETD 08/10/2026</p>", subtype="html")
    return message


def test_parse_eml_headers_and_bodies() -> None:
    parsed = parse_eml(simple_eml(with_html=True))
    assert parsed.sender == "ana@empresa.example"
    assert parsed.recipients == (
        "ops@eshipping-sintetico.example",
        "otra@eshipping-sintetico.example",
    )
    assert parsed.sent_at == datetime(2026, 9, 20, 10, 15, tzinfo=MADRID_SUMMER)
    assert parsed.subject == "BOOKING 990000101"
    assert parsed.rfc_message_id == "<id-1@empresa.example>"
    assert parsed.text_body.strip() == "ETD 08/10/2026"
    assert parsed.html_body is not None


def test_parse_eml_html_only_falls_back_to_text() -> None:
    message = EmailMessage()
    message["From"] = "ana@empresa.example"
    message.set_content("<p>Hola</p><p>ETD 08/10</p>", subtype="html")
    parsed = parse_eml(message)
    assert parsed.text_body == "Hola\n\nETD 08/10"
    assert parsed.sent_at is None
    assert parsed.rfc_message_id is None


def test_parse_eml_attachments_embedded_and_signature_images() -> None:
    container = simple_eml()
    container.add_attachment(simple_eml(), filename="M1.eml")
    container.add_attachment(
        b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="levante.pdf"
    )
    container.add_attachment(b"\x89PNG", maintype="image", subtype="png", filename="logo.png")
    parsed = parse_eml(container)
    assert len(parsed.embedded) == 1
    assert [a.filename for a in parsed.attachments] == ["levante.pdf"]
    assert parsed.attachments[0].content == b"%PDF-1.4 fake"


def test_file_parser_picks_the_format_by_extension() -> None:
    parser = MailFileParser()
    assert parser.parse(simple_eml().as_bytes(), "A.EML").subject == "BOOKING 990000101"
    with pytest.raises(ValueError, match="unsupported"):
        parser.parse(b"x", "A.pdf")


def msg_like(**overrides: Any) -> SimpleNamespace:
    data: dict[str, Any] = {
        "sender": "Ana Ejemplo <ana@empresa.example>",
        "to": "ops@x.example; otra@x.example",
        "date": datetime(2026, 9, 20, 10, 15),  # noqa: DTZ001 - msg dates may be naive
        "subject": "BOOKING 990000101",
        "messageId": "<id-1@empresa.example>",
        "body": "ETD 08/10/2026",
        "htmlBody": None,
        "attachments": [],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_parse_msg_with_embedded_message_files_and_images() -> None:
    inner = msg_like(subject="Embebido", body="", htmlBody=b"<p>Hola</p>")
    outer = msg_like(
        attachments=[
            SimpleNamespace(data=inner, mimetype=None, longFilename=None),
            SimpleNamespace(data=b"%PDF", mimetype="application/pdf", longFilename="a.pdf"),
            SimpleNamespace(data=b"%PDF", mimetype=None, longFilename=None),
            SimpleNamespace(data=b"\x89PNG", mimetype="image/png", longFilename="logo.png"),
        ]
    )
    parsed = parse_msg(outer)  # type: ignore[arg-type]
    assert parsed.sender == "ana@empresa.example"
    assert parsed.recipients == ("ops@x.example", "otra@x.example")
    assert parsed.sent_at == datetime(2026, 9, 20, 10, 15, tzinfo=UTC)
    assert [a.filename for a in parsed.attachments] == ["a.pdf", "attachment"]
    assert parsed.attachments[1].mime_type == "application/octet-stream"
    assert parsed.embedded[0].text_body == "Hola"
    assert parsed.embedded[0].html_body == "<p>Hola</p>"


def test_parse_msg_without_date_or_sender() -> None:
    parsed = parse_msg(msg_like(date=None, sender=None, to=None, subject=None))  # type: ignore[arg-type]
    assert (parsed.sender, parsed.recipients, parsed.sent_at, parsed.subject) == ("", (), None, "")


def test_folder_source_delivers_mail_files_in_name_order(tmp_path: Path) -> None:
    (tmp_path / "b.eml").write_bytes(b"B")
    (tmp_path / "a.msg").write_bytes(b"A")
    (tmp_path / "notes.txt").write_bytes(b"ignored")
    mails = list(FolderMailSource(tmp_path, "operaciones").fetch())
    assert [m.source_ref for m in mails] == ["a.msg", "b.eml"]
    assert mails[0].content == b"A"
    assert mails[0].mailbox == "operaciones"
    assert mails[0].received_at.tzinfo is UTC
