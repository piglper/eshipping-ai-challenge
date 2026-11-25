"""Use case: ingest mails (RF-01 to RF-06).

A mail file may be a real operational mail or, in the PoC sample, a container that carries
each thread as embedded mails. Every embedded mail is processed as if it had arrived on its
own. The body of a mail that carries embedded mails is the cover of a container, not an
operational message, so it is not ingested unless ``container_body_is_message`` is set. Each
mail is split into the messages of its thread; each message is dated by its own
header, cleaned and stored once per content, and each attachment is stored once per content
with its text.
"""

import hashlib
from dataclasses import dataclass
from datetime import tzinfo

from eshipping_ai.domain.model import Document, Mail, Message
from eshipping_ai.domain.ports import (
    Clock,
    DocumentParser,
    InboxStore,
    MailParser,
    MailSource,
    ObjectStore,
    ParsedMail,
    RawMail,
)
from eshipping_ai.extraction.thread import (
    ThreadSegment,
    clean_body,
    content_hash,
    split_thread,
)

NEW_MESSAGE_DEPTH = 0


@dataclass(slots=True)
class IngestReport:
    """What an ingest run did; counts only, never content."""

    mails_new: int = 0
    mails_known: int = 0
    messages_new: int = 0
    messages_known: int = 0
    documents_new: int = 0
    documents_without_text: int = 0
    failures: int = 0


class IngestMail:
    """Reads mails from a source and stores them, their messages and their documents."""

    def __init__(  # noqa: PLR0913, PLR0917 - one collaborator per port
        self,
        source: MailSource,
        parser: MailParser,
        document_parser: DocumentParser,
        store: InboxStore,
        objects: ObjectStore,
        clock: Clock,
        local_tz: tzinfo,
        *,
        container_body_is_message: bool = False,
    ) -> None:
        """Create the use case.

        Args:
            source: Where the mails come from.
            parser: Decoder of the mail files.
            document_parser: Text extractor for attachments.
            store: Persistence of mails, messages and documents.
            objects: Store for originals, clean bodies and attachments.
            clock: Current time.
            local_tz: Time zone of the mailbox, for quoted dates written without one.
            container_body_is_message: Ingest the own body of mails that carry embedded
                mails. Off by default: in the sample every container has the same fixed
                body, which is a signature, not a message.
        """
        self._source = source
        self._parser = parser
        self._document_parser = document_parser
        self._store = store
        self._objects = objects
        self._clock = clock
        self._tz = local_tz
        self._container_body_is_message = container_body_is_message

    def run(self) -> IngestReport:
        """Ingest every mail the source delivers; one bad file does not stop the run."""
        report = IngestReport()
        for raw in self._source.fetch():
            try:
                parsed = self._parser.parse(raw.content, raw.source_ref)
            except ValueError:
                report.failures += 1
                continue
            self._ingest(parsed, raw, parent_id=None, position=None, report=report)
        return report

    def _ingest(
        self,
        parsed: ParsedMail,
        raw: RawMail,
        parent_id: str | None,
        position: int | None,
        report: IngestReport,
    ) -> None:
        mail = self._mail_entity(parsed, raw, parent_id, position)
        if not self._store.add_mail(mail):
            report.mails_known += 1
            return
        report.mails_new += 1
        if self._container_body_is_message or not parsed.embedded:
            for order, segment in enumerate(split_thread(parsed.text_body, self._tz)):
                self._ingest_segment(segment, parsed, mail, report, first_documents=order == 0)
        for index, embedded in enumerate(parsed.embedded):
            self._ingest(embedded, raw, parent_id=mail.mail_id, position=index, report=report)

    def _mail_entity(
        self, parsed: ParsedMail, raw: RawMail, parent_id: str | None, position: int | None
    ) -> Mail:
        is_embedded = parent_id is not None
        digest = _canonical_hash(parsed) if is_embedded else hashlib.sha256(raw.content).hexdigest()
        key = self._objects.put(raw.content if not is_embedded else _canonical_bytes(parsed))
        return Mail(
            mail_id=f"mail-{digest[:16]}",
            rfc_message_id=parsed.rfc_message_id,
            sha256=digest,
            mailbox=raw.mailbox,
            received_at=raw.received_at,
            raw_object_key=key,
            size_bytes=len(raw.content),
            parent_mail_id=parent_id,
            source_ref=raw.source_ref,
            position=position,
        )

    def _ingest_segment(
        self,
        segment: ThreadSegment,
        parsed: ParsedMail,
        mail: Mail,
        report: IngestReport,
        *,
        first_documents: bool,
    ) -> None:
        text = clean_body(segment.body)
        is_new = segment.depth == NEW_MESSAGE_DEPTH
        sent_at = (parsed.sent_at or mail.received_at) if is_new else segment.sent_at
        if not text or sent_at is None:
            return
        digest = content_hash(text, sent_at)
        message = Message(
            message_id=f"msg-{digest[:16]}",
            content_hash=digest,
            sender_address=parsed.sender if is_new else (segment.sender or ""),
            sent_at=sent_at,
            subject=parsed.subject if is_new else (segment.subject or parsed.subject),
            clean_body_key=self._objects.put(text.encode()),
            first_seen_mail_id=mail.mail_id,
        )
        if self._store.add_message(message, mail.mail_id, segment.depth):
            report.messages_new += 1
            if first_documents:
                self._ingest_documents(parsed, message, report)
        else:
            report.messages_known += 1

    def _ingest_documents(self, parsed: ParsedMail, message: Message, report: IngestReport) -> None:
        for attachment in parsed.attachments:
            digest = hashlib.sha256(attachment.content).hexdigest()
            result = self._document_parser.parse(attachment.content, attachment.filename)
            document = Document(
                document_id=f"doc-{digest[:16]}",
                sha256=digest,
                filename=attachment.filename,
                mime_type=attachment.mime_type,
                object_key=self._objects.put(attachment.content),
                text_key=self._objects.put(result.text.encode()) if result.text else None,
                has_text_layer=result.has_text_layer,
                ocr_applied=result.ocr_applied,
                pages=result.pages or None,
            )
            if self._store.add_document(document, message.message_id):
                report.documents_new += 1
                if not result.has_text_layer and attachment.filename.lower().endswith(".pdf"):
                    report.documents_without_text += 1


def _canonical_bytes(parsed: ParsedMail) -> bytes:
    """Stable serialisation of an embedded mail, which has no bytes of its own."""
    parts = (
        parsed.rfc_message_id or "",
        parsed.sent_at.isoformat() if parsed.sent_at else "",
        parsed.sender,
        parsed.subject,
        parsed.text_body,
    )
    return "\x1f".join(parts).encode()


def _canonical_hash(parsed: ParsedMail) -> str:
    return hashlib.sha256(_canonical_bytes(parsed)).hexdigest()
