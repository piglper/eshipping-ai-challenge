"""Relational schema of the PoC (docs/05_modelo_datos.md), portable between SQLite and PostgreSQL.

Columns that are queried (keys, times, status) are real columns with indexes. The rest of an
entity is kept whole in a ``payload`` JSON column, so that the schema stays small and the
entity is rebuilt exactly as it was stored. Times are stored in UTC.

The input and observation layers are insert-only; the only updates are the status of an
observation (``superseded``) and of a verdict. Field states are a projection that can be
dropped and recomputed.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import TypeDecorator

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UtcDateTime(TypeDecorator[datetime]):
    """A timezone-aware datetime, stored as naive UTC so that every database orders it alike."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        """Convert to naive UTC; a naive value is a programming error."""
        if value is None:
            return None
        if value.tzinfo is None:
            msg = "times are stored with their time zone"
            raise ValueError(msg)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        """Return the time as an aware UTC datetime."""
        return value.replace(tzinfo=UTC) if value is not None else None


metadata = MetaData(naming_convention=NAMING)

mail = Table(
    "mail",
    metadata,
    Column("mail_id", String(40), primary_key=True),
    Column("rfc_message_id", Text),
    Column("sha256", String(64), nullable=False),
    Column("mailbox", String(200), nullable=False),
    Column("received_at", UtcDateTime, nullable=False),
    Column("raw_object_key", Text, nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("parent_mail_id", String(40), ForeignKey("mail.mail_id")),
    Index("ix_mail_sha256", "sha256"),
)

message = Table(
    "message",
    metadata,
    Column("message_id", String(40), primary_key=True),
    Column("content_hash", String(64), nullable=False, unique=True),
    Column("sender_address", Text, nullable=False),
    Column("sent_at", UtcDateTime, nullable=False),
    Column("subject", Text, nullable=False),
    Column("language", String(8)),
    Column("clean_body_key", Text, nullable=False),
    Column("first_seen_mail_id", String(40), ForeignKey("mail.mail_id"), nullable=False),
)

mail_message = Table(
    "mail_message",
    metadata,
    Column("mail_id", String(40), ForeignKey("mail.mail_id"), primary_key=True),
    Column("message_id", String(40), ForeignKey("message.message_id"), primary_key=True),
    Column("depth", Integer, nullable=False),
)

document = Table(
    "document",
    metadata,
    Column("document_id", String(40), primary_key=True),
    Column("sha256", String(64), nullable=False, unique=True),
    Column("filename", Text, nullable=False),
    Column("mime_type", String(100), nullable=False),
    Column("object_key", Text, nullable=False),
    Column("text_key", Text),
    Column("has_text_layer", Boolean, nullable=False),
    Column("ocr_applied", Boolean, nullable=False),
    Column("doc_type", String(100)),
    Column("pages", Integer),
)

message_document = Table(
    "message_document",
    metadata,
    Column("message_id", String(40), ForeignKey("message.message_id"), primary_key=True),
    Column("document_id", String(40), ForeignKey("document.document_id"), primary_key=True),
)

classification = Table(
    "classification",
    metadata,
    Column("message_id", String(40), ForeignKey("message.message_id"), primary_key=True),
    Column("mail_class", String(8), primary_key=True),
    Column("extractor_version", String(40), primary_key=True),
    Column("is_primary", Boolean, nullable=False),
    Column("payload", JSON, nullable=False),
)

association = Table(
    "association",
    metadata,
    Column("message_id", String(40), ForeignKey("message.message_id"), primary_key=True),
    Column("shipment_id", String(40), primary_key=True),
    Column("method", String(20), nullable=False),
    Column("status", String(20), nullable=False),
    Column("payload", JSON, nullable=False),
    Index("ix_association_shipment", "shipment_id"),
)

erp_snapshot = Table(
    "erp_snapshot",
    metadata,
    Column("snapshot_id", String(40), primary_key=True),
    Column("read_at", UtcDateTime, nullable=False),
    Column("source", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("row_count", Integer, nullable=False),
)

erp_record = Table(
    "erp_record",
    metadata,
    Column("snapshot_id", String(40), ForeignKey("erp_snapshot.snapshot_id"), primary_key=True),
    Column("operation", String(40), primary_key=True),
    Column("payload", JSON, nullable=False),
)

shipment_alias = Table(
    "shipment_alias",
    metadata,
    Column("alias_id", Integer, primary_key=True, autoincrement=True),
    Column("shipment_id", String(40), nullable=False),
    Column("alias_type", String(20), nullable=False),
    Column("value", String(100), nullable=False),
    Column("valid_from", UtcDateTime, nullable=False),
    Column("valid_to", UtcDateTime),
    Column("source_observation_id", String(80)),
    UniqueConstraint("alias_type", "value", "shipment_id", name="uq_alias_identity"),
    Index("ix_shipment_alias_lookup", "alias_type", "value"),
)

observation = Table(
    "observation",
    metadata,
    Column("observation_id", String(120), primary_key=True),
    Column("idempotency_key", String(64), nullable=False, unique=True),
    Column("shipment_id", String(40)),
    Column("field", String(80), nullable=False),
    Column("known_at", UtcDateTime, nullable=False),
    Column("recorded_at", UtcDateTime, nullable=False),
    Column("status", String(20), nullable=False),
    Column("superseded_at", UtcDateTime),
    Column("payload", JSON, nullable=False),
    Index("ix_observation_projection", "shipment_id", "field", "known_at"),
)

field_state = Table(
    "field_state",
    metadata,
    Column("shipment_id", String(40), primary_key=True),
    Column("field", String(80), primary_key=True),
    Column("computed_at", UtcDateTime, nullable=False),
    Column("payload", JSON, nullable=False),
)

verdict = Table(
    "verdict",
    metadata,
    Column("verdict_id", String(40), primary_key=True),
    Column("shipment_id", String(40), nullable=False),
    Column("field", String(80), nullable=False),
    Column("code", String(20), nullable=False),
    Column("status", String(20), nullable=False),
    Column("computed_at", UtcDateTime, nullable=False),
    Column("payload", JSON, nullable=False),
    Index("ix_verdict_shipment", "shipment_id", "field", "status"),
)
