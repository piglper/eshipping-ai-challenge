"""Ports of the hexagonal architecture (docs/04_arquitectura.md §6.3).

The domain and the use cases depend only on these protocols. Each one has a simple adapter
for the PoC (folder of mails, SQLite, Ollama, in-process queue) and can have a production
adapter (Microsoft Graph, PostgreSQL, a provider from ADR-0010, a managed queue) without
changing anything else.
"""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Protocol

from pydantic import AwareDatetime, Field, NonNegativeInt

from eshipping_ai.domain.model import (
    Association,
    Classification,
    Document,
    DomainModel,
    ErpRecord,
    ErpSnapshot,
    FieldState,
    Mail,
    Message,
    Observation,
    ShipmentAlias,
    Verdict,
)
from eshipping_ai.domain.vocabulary import AliasType, Priority

# --- Values exchanged through the ports ----------------------------------------


class RawMail(DomainModel):
    """A mail as delivered by a mail source, before any parsing."""

    source_ref: str
    content: bytes
    received_at: AwareDatetime
    mailbox: str


class Attachment(DomainModel):
    """A file attached to a mail (images used as signatures are dropped by the parser)."""

    filename: str
    mime_type: str
    content: bytes


class ParsedMail(DomainModel):
    """A mail decoded from its file format: headers, bodies, attachments and embedded mails."""

    sender: str
    recipients: tuple[str, ...]
    sent_at: AwareDatetime | None
    subject: str
    rfc_message_id: str | None
    text_body: str
    html_body: str | None = None
    attachments: tuple[Attachment, ...] = ()
    embedded: tuple[ParsedMail, ...] = ()


class ThreadMessage(DomainModel):
    """A stored message as it appears in one mail, with its attachments."""

    message: Message
    depth: NonNegativeInt
    documents: tuple[Document, ...] = ()
    processed: bool = False


class ThreadView(DomainModel):
    """The messages of one mail, newest first: the context in which each one is read."""

    mail: Mail
    messages: tuple[ThreadMessage, ...]


class ParsedDocument(DomainModel):
    """Text extracted from an attachment."""

    text: str | None
    has_text_layer: bool
    pages: NonNegativeInt
    ocr_applied: bool = False


class LLMRequest(DomainModel):
    """One structured-output call to a language model."""

    prompt_version: str
    instructions: str
    content: str
    json_schema: Mapping[str, object]
    examples: Sequence[tuple[str, str]] = ()


class LLMResponse(DomainModel):
    """Answer of a language model, with what is needed to measure its cost."""

    output: Mapping[str, object]
    model: str
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    cached_tokens: NonNegativeInt = 0
    latency_ms: NonNegativeInt


class Task(DomainModel):
    """A unit of work waiting between two stages of the pipeline."""

    task_id: str
    stage: str
    payload_ref: str
    idempotency_key: str
    priority: Priority = Priority.P3
    attempts: NonNegativeInt = 0
    available_at: AwareDatetime
    last_error: str | None = Field(default=None, max_length=1000)


# --- Ports ---------------------------------------------------------------------


class Clock(Protocol):
    """Source of the current time; injected so that tests are deterministic."""

    def now(self) -> datetime:
        """Return the current time with its time zone."""
        ...


class MailSource(Protocol):
    """Where mails come from: a folder in the PoC, the corporate mailbox in production."""

    def fetch(self) -> Iterable[RawMail]:
        """Yield the mails not delivered yet."""
        ...


class ObjectStore(Protocol):
    """Store for large and personal content: originals, clean bodies, attachments."""

    def put(self, content: bytes) -> str:
        """Store content under a key derived from its hash and return the key."""
        ...

    def get(self, key: str) -> bytes:
        """Return the content stored under a key."""
        ...


class MailParser(Protocol):
    """Decodes mail files (``.eml``, ``.msg``) into :class:`ParsedMail`."""

    def parse(self, content: bytes, filename: str) -> ParsedMail:
        """Decode a mail file; embedded mails are returned in ``embedded``."""
        ...


class DocumentParser(Protocol):
    """Text extraction from attachments."""

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        """Extract the text of an attachment."""
        ...


class LLMClient(Protocol):
    """Language model with structured output (ADR-0005, ADR-0010)."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one call and return output that already matches the requested schema."""
        ...


class ERPGateway(Protocol):
    """Read-only access to the ERP; the system never writes to it (RF-55)."""

    def read(self) -> tuple[ErpSnapshot, Sequence[ErpRecord]]:
        """Read the ERP and return the snapshot with its rows."""
        ...


class InboxStore(Protocol):
    """Persistence of the input layer: mails, messages and documents."""

    def add_mail(self, mail: Mail) -> bool:
        """Store a mail; return False if it was already stored (idempotency)."""
        ...

    def add_message(self, message: Message, mail_id: str, depth: int) -> bool:
        """Store a message and link it to the mail it appears in.

        The link is always created; the return value is False if the message (identified
        by its content hash) was already stored, so a quoted message is stored once.
        """
        ...

    def add_document(self, document: Document, message_id: str) -> bool:
        """Store an attachment once per content and link it to a message."""
        ...


class InboxReader(Protocol):
    """Read side of the input layer: which mails still have messages to process."""

    def unprocessed_mail_ids(self) -> Sequence[str]:
        """Return the mails with a message that has not been classified, oldest first."""
        ...

    def thread(self, mail_id: str) -> ThreadView:
        """Return the messages of a mail, with their attachments and their state."""
        ...


class ProcessingStore(Protocol):
    """Persistence of the classification and association of messages."""

    def add_classifications(self, classifications: Iterable[Classification]) -> int:
        """Insert classifications, skipping those already stored; return how many were new."""
        ...

    def add_associations(self, associations: Iterable[Association]) -> int:
        """Insert associations, skipping those already stored; return how many were new."""
        ...

    def associations_for(self, shipment_id: str) -> Sequence[Association]:
        """Return the messages associated with a shipment."""
        ...


class ObservationStore(Protocol):
    """Persistence of observations, which are never updated in place."""

    def add_observations(self, observations: Iterable[Observation]) -> int:
        """Insert observations, skipping those already stored; return how many were new."""
        ...

    def observations_for(
        self, shipment_id: str, as_of: datetime | None = None
    ) -> Sequence[Observation]:
        """Return the observations of a shipment, as they were known at a given time.

        With ``as_of``, only what the sources had said (``known_at``) and the system had
        recorded (``recorded_at``) by then is returned, and an observation superseded
        later is returned as active (RF-61).
        """
        ...

    def mark_superseded(self, observation_id: str, superseded_by: str, at: datetime) -> None:
        """Mark an observation as superseded by another; the only change allowed to one."""
        ...


class AliasStore(Protocol):
    """The association index: identifiers under which each shipment is known."""

    def find_aliases(self, alias_type: AliasType, value: str) -> Sequence[ShipmentAlias]:
        """Return the shipments known under an identifier."""
        ...

    def add_alias(self, alias: ShipmentAlias) -> None:
        """Register a new identifier for a shipment."""
        ...


class ErpStore(Protocol):
    """Persistence of ERP reads."""

    def add_erp_snapshot(self, snapshot: ErpSnapshot, records: Iterable[ErpRecord]) -> None:
        """Store an ERP read with its rows."""
        ...


class ProjectionStore(Protocol):
    """Persistence of the recomputable conclusions."""

    def save_field_states(self, states: Iterable[FieldState]) -> None:
        """Replace the projection of the given fields."""
        ...

    def save_verdicts(self, verdicts: Iterable[Verdict]) -> None:
        """Store verdicts; the previous verdict of the same field becomes superseded."""
        ...

    def field_states_for(self, shipment_id: str) -> Sequence[FieldState]:
        """Return the current projection of a shipment."""
        ...

    def verdicts_for(self, shipment_id: str) -> Sequence[Verdict]:
        """Return the verdicts of a shipment that are not superseded."""
        ...


class Repository(
    InboxStore,
    InboxReader,
    ProcessingStore,
    ObservationStore,
    AliasStore,
    ErpStore,
    ProjectionStore,
    Protocol,
):
    """Persistence of the domain entities (docs/05_modelo_datos.md).

    Use cases depend on the narrow store they need; adapters implement the whole thing.
    """


class Notifier(Protocol):
    """Urgent notices to operations (only P1, grouped by shipment)."""

    def notify(self, shipment_id: str, verdicts: Sequence[Verdict]) -> None:
        """Send one notice about the urgent verdicts of a shipment."""
        ...


class TaskQueue(Protocol):
    """Queue between stages (ADR-0007): in-process in the PoC, PostgreSQL in production."""

    def enqueue(self, task: Task) -> bool:
        """Add a task; return False if a task with the same idempotency key exists."""
        ...

    def claim(self, stage: str) -> Task | None:
        """Take the next available task of a stage, most urgent first."""
        ...

    def complete(self, task_id: str) -> None:
        """Mark a task as done."""
        ...

    def fail(self, task_id: str, error: str) -> None:
        """Record a failure; the task is retried later or moved to the dead-letter queue."""
        ...
