"""Mail sources and parsers for files on disk: ``.eml`` and ``.msg``.

``FolderMailSource`` is the PoC's mail source (``MailSource``); in production the same port
is implemented against the corporate mailbox. ``MailFileParser`` decodes both formats into
the same :class:`ParsedMail`, including mails embedded as attachments (the sample's
containers carry each thread as ``.msg`` or ``message/rfc822`` attachments, RF-02).
"""

import email
import email.policy
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import getaddresses
from pathlib import Path
from typing import Protocol, cast

import extract_msg
from extract_msg.exceptions import ExMsgBaseException

from eshipping_ai.domain.ports import Attachment, ParsedMail, RawMail
from eshipping_ai.extraction.thread import html_to_text

SUPPORTED_SUFFIXES = (".eml", ".msg")
_IGNORED_ATTACHMENT_TYPES = ("image/",)
"""Signature logos and banners are noise (docs/01_analisis_datos.md §2.1)."""


class FolderMailSource:
    """Delivers every ``.eml`` and ``.msg`` file of a folder, in name order."""

    def __init__(self, folder: Path, mailbox: str) -> None:
        """Create a source.

        Args:
            folder: Folder with the mail files.
            mailbox: Name recorded as the mailbox of the mails.
        """
        self._folder = folder
        self._mailbox = mailbox

    def fetch(self) -> Iterator[RawMail]:
        """Yield the mails of the folder."""
        for path in sorted(self._folder.iterdir()):
            if path.suffix.lower() in SUPPORTED_SUFFIXES:
                stat = path.stat()
                yield RawMail(
                    source_ref=path.name,
                    content=path.read_bytes(),
                    received_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                    mailbox=self._mailbox,
                )


class MailFileParser:
    """Decodes ``.eml`` and ``.msg`` files, chosen by the file name."""

    def parse(self, content: bytes, filename: str) -> ParsedMail:
        """Decode a mail file.

        Args:
            content: Bytes of the file.
            filename: Name of the file, used to pick the format.

        Returns:
            The decoded mail with its attachments and embedded mails.

        Raises:
            ValueError: If the extension is not supported.
        """
        suffix = Path(filename).suffix.lower()
        if suffix == ".eml":
            return parse_eml(email.message_from_bytes(content, policy=email.policy.default))
        if suffix == ".msg":
            try:
                opened = extract_msg.openMsg(content)
            except (OSError, ExMsgBaseException) as error:
                msg = f"{filename}: not a readable Outlook message"
                raise ValueError(msg) from error
            return parse_msg(cast("_MsgLike", opened))
        msg = f"unsupported mail format: {filename!r}"
        raise ValueError(msg)


# --- .eml ----------------------------------------------------------------------------------


def _addresses(message: EmailMessage, header: str) -> tuple[str, ...]:
    return tuple(address for _, address in getaddresses(message.get_all(header, [])) if address)


def _body(message: EmailMessage, kind: str) -> str | None:
    part = message.get_body(preferencelist=(kind,))
    return part.get_content() if part is not None else None


def parse_eml(message: EmailMessage) -> ParsedMail:
    """Convert a MIME message to a :class:`ParsedMail`.

    Args:
        message: Message parsed with the default policy.

    Returns:
        The decoded mail.
    """
    html = _body(message, "html")
    text = _body(message, "plain") or (html_to_text(html) if html else "")
    attachments: list[Attachment] = []
    embedded: list[ParsedMail] = []
    for part in message.iter_attachments():
        content_type = part.get_content_type()
        if content_type == "message/rfc822":
            inner = part.get_content()
            if isinstance(inner, EmailMessage):
                embedded.append(parse_eml(inner))
        elif not content_type.startswith(_IGNORED_ATTACHMENT_TYPES):
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                attachments.append(
                    Attachment(
                        filename=part.get_filename() or "attachment",
                        mime_type=content_type,
                        content=payload,
                    )
                )
    date = message["Date"]
    sent_at = date.datetime if date is not None else None
    return ParsedMail(
        sender=next(iter(_addresses(message, "From")), ""),
        recipients=_addresses(message, "To"),
        sent_at=sent_at if sent_at is not None and sent_at.tzinfo is not None else None,
        subject=str(message["Subject"] or ""),
        rfc_message_id=str(message["Message-ID"]) if message["Message-ID"] else None,
        text_body=text,
        html_body=html,
        attachments=tuple(attachments),
        embedded=tuple(embedded),
    )


# --- .msg ----------------------------------------------------------------------------------


class _MsgAttachment(Protocol):
    """The part of an ``extract_msg`` attachment that the parser uses."""

    @property
    def data(self) -> object:
        """Bytes of a file, or the embedded message."""
        ...

    @property
    def mimetype(self) -> str | None:
        """Media type of the attachment."""
        ...

    @property
    def longFilename(self) -> str | None:  # noqa: N802 - name defined by the library
        """File name of the attachment."""
        ...


class _MsgLike(Protocol):
    """The part of an ``extract_msg`` message that the parser uses."""

    sender: str | None
    to: str | None
    date: object
    subject: str | None
    messageId: str | None  # noqa: N815 - name defined by the library
    body: str | None
    htmlBody: bytes | None  # noqa: N815 - name defined by the library

    @property
    def attachments(self) -> Sequence[_MsgAttachment]:
        """Attached files and embedded messages."""
        ...


def _msg_sent_at(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return None


def parse_msg(message: _MsgLike) -> ParsedMail:
    """Convert an Outlook ``.msg`` to a :class:`ParsedMail`, recursively.

    Args:
        message: A message opened with ``extract_msg``.

    Returns:
        The decoded mail.
    """
    raw_html = message.htmlBody
    html = raw_html.decode("utf-8", errors="replace") if isinstance(raw_html, bytes) else None
    text = message.body or (html_to_text(html) if html else "")
    attachments: list[Attachment] = []
    embedded: list[ParsedMail] = []
    for attachment in message.attachments:
        data = attachment.data
        mime = attachment.mimetype or "application/octet-stream"
        if isinstance(data, bytes):
            if not mime.startswith(_IGNORED_ATTACHMENT_TYPES):
                name = attachment.longFilename or "attachment"
                attachments.append(Attachment(filename=name, mime_type=mime, content=data))
        elif hasattr(data, "attachments"):
            embedded.append(parse_msg(cast("_MsgLike", data)))
    sender = message.sender or ""
    return ParsedMail(
        sender=next((address for _, address in getaddresses([sender]) if address), sender),
        recipients=tuple(part.strip() for part in (message.to or "").split(";") if part.strip()),
        sent_at=_msg_sent_at(message.date),
        subject=message.subject or "",
        rfc_message_id=message.messageId,
        text_body=text,
        html_body=html,
        attachments=tuple(attachments),
        embedded=tuple(embedded),
    )
