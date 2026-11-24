"""Split a mail body into the messages of its thread and clean each one.

A reply or a forward carries the previous messages as quoted text under a header block
(``De:``/``From:``, ``Enviado:``/``Sent:``, ``Asunto:``/``Subject:``) or a one-line
attribution (``On ... wrote:``). Each message is dated by its own header (RF-03, A-14),
cleaned of signatures, legal notices and image placeholders (RF-04), and identified by a
hash of its normalised text so that a message quoted in twenty mails is stored once.
"""

import hashlib
import html
import re
from dataclasses import dataclass
from datetime import datetime, tzinfo
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser

_HEADER_LOOKAHEAD = 8
"""How many lines after ``De:``/``From:`` may hold the rest of a quoted header block."""

_FROM_RE = re.compile(r"^\s*(?:De|From)\s*:\s*(?P<value>.+)$", re.IGNORECASE)
_SENT_RE = re.compile(
    r"^\s*(?:Enviado(?: el)?|Sent|Fecha|Date)\s*:\s*(?P<value>.+)$", re.IGNORECASE
)
_SUBJECT_RE = re.compile(r"^\s*(?:Asunto|Subject)\s*:\s*(?P<value>.*)$", re.IGNORECASE)
_ATTRIBUTION_RE = re.compile(
    r"^\s*(?:On|El)\s+(?P<date>.+?),\s*(?P<sender>[^,]+?)\s+(?:wrote|escribió)\s*:\s*$",
    re.IGNORECASE,
)
_SEPARATOR_RE = re.compile(
    r"^\s*-{2,}\s*(?:Original Message|Mensaje original|Forwarded message|Mensaje reenviado)"
    r"\s*-{2,}\s*$",
    re.IGNORECASE,
)
_QUOTE_PREFIX_RE = re.compile(r"^(?:\s*>)+ ?", re.MULTILINE)
_IMAGE_RE = re.compile(r"\[cid:[^\]]*\]|<image\d+\.\w+>|\[image: [^\]]*\]", re.IGNORECASE)
_SIGNATURE_DELIMITER_RE = re.compile(r"^--\s*$")
_CLOSING_RE = re.compile(
    r"^\s*(?:un saludo|saludos(?: cordiales)?|atentamente|cordialmente|"
    r"best regards|kind regards|regards|thanks and regards|many thanks and best regards)"
    r"\s*[,.!]?\s*$",
    re.IGNORECASE,
)
_DISCLAIMER_RE = re.compile(
    r"aviso legal|confidencial|confidentiality|this e-?mail (?:and any|is)|"
    r"protección de datos|data protection|antes de imprimir|before printing|"
    r"if you are not the intended recipient|si usted no es el destinatario",
    re.IGNORECASE,
)

_MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("enero", "january", "jan", "ene"),
            ("febrero", "february", "feb"),
            ("marzo", "march", "mar"),
            ("abril", "april", "apr", "abr"),
            ("mayo", "may"),
            ("junio", "june", "jun"),
            ("julio", "july", "jul"),
            ("agosto", "august", "aug", "ago"),
            ("septiembre", "setiembre", "september", "sep", "sept"),
            ("octubre", "october", "oct"),
            ("noviembre", "november", "nov"),
            ("diciembre", "december", "dec", "dic"),
        ],
        start=1,
    )
    for name in names
}
_NUMERIC_DATE_RE = re.compile(
    r"(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})\D+(?P<h>\d{1,2}):(?P<min>\d{2})"
)
_DAY_MONTH_RE = re.compile(
    r"(?P<d>\d{1,2})\s+(?:de\s+)?(?P<month>[a-záéíóú]+)\.?\s+(?:de\s+)?(?P<y>\d{4})"
    r"\D+?(?P<h>\d{1,2}):(?P<min>\d{2})(?:\s*(?P<ampm>[AaPp]\.?\s?[Mm]\.?))?"
)
_MONTH_DAY_RE = re.compile(
    r"(?P<month>[A-Za-z]+)\.?\s+(?P<d>\d{1,2}),?\s+(?P<y>\d{4})"
    r"\D+?(?P<h>\d{1,2}):(?P<min>\d{2})(?:\s*(?P<ampm>[AaPp]\.?\s?[Mm]\.?))?"
)
_NOON = 12


@dataclass(frozen=True, slots=True)
class ThreadSegment:
    """One message of a thread, as found in the body of a mail.

    ``depth`` is 0 for the new message written in this mail and 1, 2, ... for the quoted
    ones, from the most recent to the oldest. Quoted messages carry the sender, date and
    subject of their quoted header; the new message takes them from the mail headers.
    """

    depth: int
    body: str
    sender: str | None
    sent_at: datetime | None
    subject: str | None


class _TextExtractor(HTMLParser):
    _BLOCKS = frozenset({"p", "div", "br", "tr", "li", "table", "h1", "h2", "h3", "hr"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"style", "script", "head"}:
            self._skip += 1
        elif tag in self._BLOCKS:
            self.parts.append("\n")
        elif tag == "td":
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script", "head"} and self._skip:
            self._skip -= 1
        elif tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(markup: str) -> str:
    """Convert an HTML body to plain text, keeping line breaks between blocks.

    Args:
        markup: HTML of the mail body.

    Returns:
        The visible text, with one line per block and collapsed spaces.
    """
    extractor = _TextExtractor()
    extractor.feed(markup)
    extractor.close()
    text = html.unescape("".join(extractor.parts)).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def parse_header_date(value: str, default_tz: tzinfo) -> datetime | None:
    """Parse the date of a quoted header, in the formats Outlook and Gmail write.

    Quoted headers carry no time zone, except RFC 2822 dates; they are rendered in the
    time zone of whoever replied or forwarded, assumed to be ``default_tz``.

    Args:
        value: Text after ``Enviado:``, ``Sent:``, ``Fecha:`` or ``Date:``.
        default_tz: Time zone for dates written without one.

    Returns:
        An aware datetime, or None if the format is not recognised.
    """
    try:
        parsed = parsedate_to_datetime(value)
    except TypeError, ValueError, IndexError:
        parsed = None
    if parsed is not None and parsed.tzinfo is not None:
        return parsed
    for pattern in (_NUMERIC_DATE_RE, _DAY_MONTH_RE, _MONTH_DAY_RE):
        match = pattern.search(value)
        if match is None:
            continue
        groups = match.groupdict()
        month = int(groups["m"]) if "m" in groups else _MONTHS.get(groups["month"].lower())
        if month is None:
            continue
        hour = int(groups["h"])
        ampm = (groups.get("ampm") or "").lower().replace(".", "").replace(" ", "")
        if ampm == "pm" and hour < _NOON:
            hour += _NOON
        elif ampm == "am" and hour == _NOON:
            hour = 0
        try:
            return datetime(
                int(groups["y"]),
                month,
                int(groups["d"]),
                hour,
                int(groups["min"]),
                tzinfo=default_tz,
            )
        except ValueError:
            return None
    return None


def _sender_of(value: str) -> str:
    """Address of a quoted sender if present; otherwise the name, lower-cased."""
    name, address = parseaddr(value.strip())
    if "@" in address:
        return address.lower()
    return (name or value).strip().strip('"').lower()


def _header_at(lines: list[str], index: int) -> tuple[int, str, str | None, str | None] | None:
    """Recognise a quoted header block starting at ``lines[index]``.

    Returns:
        The index of the first line after the block, the sender, the date and the subject;
        or None if there is no header block here.
    """
    attribution = _ATTRIBUTION_RE.match(lines[index])
    if attribution:
        return index + 1, attribution["sender"], attribution["date"], None
    sender = _FROM_RE.match(lines[index])
    if not sender:
        return None
    sent: str | None = None
    subject: str | None = None
    end = index + 1
    for position in range(index + 1, min(index + 1 + _HEADER_LOOKAHEAD, len(lines))):
        line = lines[position]
        if (match := _SENT_RE.match(line)) and sent is None:
            sent, end = match["value"], position + 1
        elif match := _SUBJECT_RE.match(line):
            subject, end = match["value"], position + 1
            break
        elif not line.strip():
            break
    if sent is None or subject is None:
        return None
    return end, sender["value"], sent, subject


def split_thread(body: str, default_tz: tzinfo) -> list[ThreadSegment]:
    """Split a mail body into its new message and its quoted messages.

    Args:
        body: Plain-text body of the mail.
        default_tz: Time zone for quoted dates written without one.

    Returns:
        The segments, the new message first (depth 0) and then the quoted ones.
    """
    lines = _QUOTE_PREFIX_RE.sub("", body.replace("\r\n", "\n")).split("\n")
    segments: list[ThreadSegment] = []
    current: list[str] = []
    header: tuple[str | None, datetime | None, str | None] = (None, None, None)
    index = 0
    while index < len(lines):
        found = _header_at(lines, index)
        if found is None:
            current.append(lines[index])
            index += 1
            continue
        if current and _SEPARATOR_RE.match(current[-1]):
            current.pop()
        segments.append(ThreadSegment(len(segments), "\n".join(current), *header))
        end, sender, sent, subject = found
        header = (
            _sender_of(sender),
            parse_header_date(sent, default_tz) if sent else None,
            subject,
        )
        current = []
        index = end
    segments.append(ThreadSegment(len(segments), "\n".join(current), *header))
    return segments


def clean_body(text: str) -> str:
    """Remove image placeholders, signatures and legal notices from one message.

    Everything after a signature delimiter (``--``) or a closing line (``Un saludo``,
    ``Best regards``...) is dropped, and so is any paragraph that reads like a legal
    notice.

    Args:
        text: Text of one message of the thread.

    Returns:
        The cleaned text, possibly empty.
    """
    kept: list[str] = []
    for line in _IMAGE_RE.sub("", text).split("\n"):
        if _SIGNATURE_DELIMITER_RE.match(line) or _CLOSING_RE.match(line):
            break
        kept.append(line.rstrip())
    paragraphs = re.split(r"\n\s*\n", "\n".join(kept))
    useful = [p.strip() for p in paragraphs if p.strip() and not _DISCLAIMER_RE.search(p)]
    return "\n\n".join(useful)


def content_hash(clean_text: str, sent_at: datetime | None) -> str:
    """Identify a message by its normalised text and the minute it was sent.

    The minute tells apart short identical messages (``Gracias``) sent at different
    times; quoted headers only show minutes, so seconds are ignored.

    Args:
        clean_text: Output of :func:`clean_body`.
        sent_at: Date of the message, if known.

    Returns:
        Hex SHA-256 digest.
    """
    normalised = " ".join(clean_text.casefold().split())
    minute = sent_at.astimezone().strftime("%Y-%m-%dT%H:%M%z") if sent_at else ""
    return hashlib.sha256(f"{minute}\x1f{normalised}".encode()).hexdigest()
