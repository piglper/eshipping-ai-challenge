from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from eshipping_ai.adapters.mail_files import FolderMailSource, MailFileParser
from eshipping_ai.adapters.object_store import LocalObjectStore
from eshipping_ai.adapters.pdf_text import PdfTextParser
from eshipping_ai.application.ingest import IngestMail, IngestReport
from tests.adapters.test_object_store_and_pdf import make_pdf

MADRID = ZoneInfo("Europe/Madrid")


def ingest(folder: Path, objects: Path, inbox, clock) -> IngestReport:  # type: ignore[no-untyped-def]
    return IngestMail(
        FolderMailSource(folder, "operaciones"),
        MailFileParser(),
        PdfTextParser(),
        inbox,
        LocalObjectStore(objects),
        clock,
        MADRID,
    ).run()


def test_synthetic_set_is_unpacked_split_and_deduplicated(synthetic_dir, tmp_path, inbox, clock):  # type: ignore[no-untyped-def]
    report = ingest(synthetic_dir / "mails", tmp_path, inbox, clock)
    # 4 containers + 13 embedded mails + 1 noise mail
    assert report.mails_new == 18
    assert sum(1 for m in inbox.mails.values() if m.parent_mail_id) == 13
    # The forward in ES26900002 quotes the carrier's notice, which is also its own mail.
    assert report.messages_known == 1
    assert report.messages_new == 14
    assert report.failures == 0


def test_each_mail_keeps_its_file_and_the_order_of_the_embedded_ones(
    synthetic_dir, tmp_path, inbox, clock
):  # type: ignore[no-untyped-def]
    ingest(synthetic_dir / "mails", tmp_path, inbox, clock)
    embedded = [
        m for m in inbox.mails.values() if m.source_ref == "ES26900003.eml" and m.parent_mail_id
    ]
    assert sorted(m.position for m in embedded) == [0, 1, 2, 3]
    containers = [m for m in inbox.mails.values() if not m.parent_mail_id]
    assert {m.source_ref for m in containers} >= {"ES26900001.eml", "N1.eml"}
    assert all(m.position is None for m in containers)


def test_every_message_is_dated_by_its_own_header(synthetic_dir, tmp_path, inbox, clock):  # type: ignore[no-untyped-def]
    ingest(synthetic_dir / "mails", tmp_path, inbox, clock)
    quoted = [
        message
        for message in inbox.messages.values()
        if message.subject == "ROLLOVER NOTICE - BKG 990000202"
    ]
    assert len(quoted) == 1
    assert quoted[0].sent_at == datetime(2026, 9, 29, 10, 15, tzinfo=MADRID)
    assert quoted[0].sender_address == "bookings@naviera-ficticia.example"
    forward = next(m for m in inbox.messages.values() if m.subject.startswith("RV:"))
    assert forward.sender_address == "operaciones@eshipping-sintetico.example"
    assert forward.sent_at == datetime(2026, 9, 29, 12, 30, tzinfo=MADRID)


def test_clean_bodies_have_no_signature_or_legal_notice(synthetic_dir, tmp_path, inbox, clock):  # type: ignore[no-untyped-def]
    ingest(synthetic_dir / "mails", tmp_path, inbox, clock)
    store = LocalObjectStore(tmp_path)
    texts = [store.get(m.clean_body_key).decode() for m in inbox.messages.values()]
    assert all("AVISO LEGAL" not in text and "Customer Service Team" not in text for text in texts)
    assert any("New vessel / voyage: CELESTE FICTICIA / 013W" in text for text in texts)


def test_ingest_is_idempotent(synthetic_dir, tmp_path, inbox, clock):  # type: ignore[no-untyped-def]
    ingest(synthetic_dir / "mails", tmp_path, inbox, clock)
    mails, messages = len(inbox.mails), len(inbox.messages)
    again = ingest(synthetic_dir / "mails", tmp_path, inbox, clock)
    assert again.mails_new == 0
    assert again.mails_known == 5  # the containers; their embedded mails are not revisited
    assert (len(inbox.mails), len(inbox.messages)) == (mails, messages)


def test_documents_are_stored_once_and_scans_are_flagged(tmp_path, inbox, clock):  # type: ignore[no-untyped-def]
    folder = tmp_path / "in"
    folder.mkdir()
    pdf = make_pdf(["LEVANTE concedido", "Contenedor SYNU1000019"])
    for number, subject in enumerate(("LEVANTE A", "LEVANTE B"), start=1):
        mail = EmailMessage()
        mail["From"] = "Aduanas <despachos@aduanas-ejemplo.example>"
        mail["To"] = "operaciones@eshipping-sintetico.example"
        mail["Subject"] = subject
        mail["Date"] = format_datetime(datetime(2026, 10, 6, 11, number, tzinfo=UTC))
        mail.set_content(f"Adjunto el levante {number}.")
        mail.add_attachment(pdf, maintype="application", subtype="pdf", filename="levante.pdf")
        mail.add_attachment(
            make_pdf([]), maintype="application", subtype="pdf", filename="escaneo.pdf"
        )
        (folder / f"{number}.eml").write_bytes(mail.as_bytes())
    report = ingest(folder, tmp_path / "objects", inbox, clock)
    assert report.messages_new == 2
    assert report.documents_new == 2  # the same two files attached to two mails
    assert report.documents_without_text == 1
    assert len(inbox.document_links) == 4
    store = LocalObjectStore(tmp_path / "objects")
    with_text = next(d for d in inbox.documents.values() if d.has_text_layer)
    assert with_text.text_key is not None
    assert "SYNU1000019" in store.get(with_text.text_key).decode()


def test_a_bad_file_does_not_stop_the_run(tmp_path, inbox, clock):  # type: ignore[no-untyped-def]
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "broken.msg").write_bytes(b"not an outlook file")
    report = ingest(folder, tmp_path / "objects", inbox, clock)
    assert report.failures == 1


def container_with_cover_note(folder: Path) -> None:
    folder.mkdir()
    inner = EmailMessage()
    inner["From"] = "bookings@naviera-ficticia.example"
    inner["Subject"] = "BOOKING CONFIRMATION 990000101"
    inner["Date"] = format_datetime(datetime(2026, 9, 20, 10, 15, tzinfo=UTC))
    inner.set_content("ETD 08/10/2026")
    outer = EmailMessage()
    outer["From"] = "operaciones@eshipping-sintetico.example"
    outer["Subject"] = "Expediente ES26900001"
    outer["Date"] = format_datetime(datetime(2026, 9, 21, 9, 0, tzinfo=UTC))
    outer.set_content("Nota interna sobre este expediente.")
    outer.add_attachment(inner, filename="M1.eml")
    (folder / "container.eml").write_bytes(outer.as_bytes())


def test_the_body_of_a_container_is_not_a_message_unless_asked(tmp_path, inbox, clock):  # type: ignore[no-untyped-def]
    container_with_cover_note(tmp_path / "in")
    default = ingest(tmp_path / "in", tmp_path / "o1", inbox, clock)
    assert (default.mails_new, default.messages_new) == (2, 1)

    other = type(inbox)()
    report = IngestMail(
        FolderMailSource(tmp_path / "in", "operaciones"),
        MailFileParser(),
        PdfTextParser(),
        other,
        LocalObjectStore(tmp_path / "o2"),
        clock,
        MADRID,
        container_body_is_message=True,
    ).run()
    assert (report.mails_new, report.messages_new) == (2, 2)
