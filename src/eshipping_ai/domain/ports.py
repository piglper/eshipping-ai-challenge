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


class Repository(Protocol):
    """Persistence of the domain entities (docs/05_modelo_datos.md)."""

    def add_mail(self, mail: Mail) -> bool:
        """Store a mail; return False if it was already stored (idempotency)."""
        ...

    def find_message_by_hash(self, content_hash: str) -> Message | None:
        """Return the message with that content hash, if it is already known."""
        ...

    def add_message(self, message: Message, mail_id: str, depth: int) -> bool:
        """Store a message and link it to the mail it appears in; False if already known."""
        ...

    def add_observations(self, observations: Iterable[Observation]) -> int:
        """Insert observations, skipping those already stored; return how many were new."""
        ...

    def observations_for(
        self, shipment_id: str, as_of: datetime | None = None
    ) -> Sequence[Observation]:
        """Return the observations of a shipment, as they were known at a given time."""
        ...

    def find_aliases(self, alias_type: AliasType, value: str) -> Sequence[ShipmentAlias]:
        """Return the shipments known under an identifier."""
        ...

    def add_alias(self, alias: ShipmentAlias) -> None:
        """Register a new identifier for a shipment."""
        ...

    def add_erp_snapshot(self, snapshot: ErpSnapshot, records: Iterable[ErpRecord]) -> None:
        """Store an ERP read with its rows."""
        ...

    def save_field_states(self, states: Iterable[FieldState]) -> None:
        """Replace the projection of the given fields."""
        ...

    def save_verdicts(self, verdicts: Iterable[Verdict]) -> None:
        """Store verdicts; the previous verdict of the same field becomes superseded."""
        ...


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
