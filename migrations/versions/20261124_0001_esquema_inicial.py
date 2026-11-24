"""Esquema inicial (docs/05_modelo_datos.md): entrada, observaciones y proyecciones.

UtcDateTime se guarda como DateTime en UTC sin zona; la migración no depende del código.

Revision ID: 0001
Revises:
Create Date: 2026-11-24 09:41:23.840612
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document",
        sa.Column("document_id", sa.String(length=40), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("text_key", sa.Text(), nullable=True),
        sa.Column("has_text_layer", sa.Boolean(), nullable=False),
        sa.Column("ocr_applied", sa.Boolean(), nullable=False),
        sa.Column("doc_type", sa.String(length=100), nullable=True),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("document_id", name=op.f("pk_document")),
        sa.UniqueConstraint("sha256", name=op.f("uq_document_sha256")),
    )
    op.create_table(
        "erp_snapshot",
        sa.Column("snapshot_id", sa.String(length=40), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id", name=op.f("pk_erp_snapshot")),
    )
    op.create_table(
        "field_state",
        sa.Column("shipment_id", sa.String(length=40), nullable=False),
        sa.Column("field", sa.String(length=80), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("shipment_id", "field", name=op.f("pk_field_state")),
    )
    op.create_table(
        "mail",
        sa.Column("mail_id", sa.String(length=40), nullable=False),
        sa.Column("rfc_message_id", sa.Text(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mailbox", sa.String(length=200), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("raw_object_key", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("parent_mail_id", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_mail_id"], ["mail.mail_id"], name=op.f("fk_mail_parent_mail_id_mail")
        ),
        sa.PrimaryKeyConstraint("mail_id", name=op.f("pk_mail")),
    )
    with op.batch_alter_table("mail", schema=None) as batch_op:
        batch_op.create_index("ix_mail_sha256", ["sha256"], unique=False)

    op.create_table(
        "observation",
        sa.Column("observation_id", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("shipment_id", sa.String(length=40), nullable=True),
        sa.Column("field", sa.String(length=80), nullable=False),
        sa.Column("known_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("superseded_at", sa.DateTime(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("observation_id", name=op.f("pk_observation")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_observation_idempotency_key")),
    )
    with op.batch_alter_table("observation", schema=None) as batch_op:
        batch_op.create_index(
            "ix_observation_projection", ["shipment_id", "field", "known_at"], unique=False
        )

    op.create_table(
        "shipment_alias",
        sa.Column("alias_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shipment_id", sa.String(length=40), nullable=False),
        sa.Column("alias_type", sa.String(length=20), nullable=False),
        sa.Column("value", sa.String(length=100), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("source_observation_id", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("alias_id", name=op.f("pk_shipment_alias")),
        sa.UniqueConstraint("alias_type", "value", "shipment_id", name="uq_alias_identity"),
    )
    with op.batch_alter_table("shipment_alias", schema=None) as batch_op:
        batch_op.create_index("ix_shipment_alias_lookup", ["alias_type", "value"], unique=False)

    op.create_table(
        "verdict",
        sa.Column("verdict_id", sa.String(length=40), nullable=False),
        sa.Column("shipment_id", sa.String(length=40), nullable=False),
        sa.Column("field", sa.String(length=80), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("verdict_id", name=op.f("pk_verdict")),
    )
    with op.batch_alter_table("verdict", schema=None) as batch_op:
        batch_op.create_index(
            "ix_verdict_shipment", ["shipment_id", "field", "status"], unique=False
        )

    op.create_table(
        "erp_record",
        sa.Column("snapshot_id", sa.String(length=40), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["erp_snapshot.snapshot_id"],
            name=op.f("fk_erp_record_snapshot_id_erp_snapshot"),
        ),
        sa.PrimaryKeyConstraint("snapshot_id", "operation", name=op.f("pk_erp_record")),
    )
    op.create_table(
        "message",
        sa.Column("message_id", sa.String(length=40), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("sender_address", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("clean_body_key", sa.Text(), nullable=False),
        sa.Column("first_seen_mail_id", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(
            ["first_seen_mail_id"],
            ["mail.mail_id"],
            name=op.f("fk_message_first_seen_mail_id_mail"),
        ),
        sa.PrimaryKeyConstraint("message_id", name=op.f("pk_message")),
        sa.UniqueConstraint("content_hash", name=op.f("uq_message_content_hash")),
    )
    op.create_table(
        "mail_message",
        sa.Column("mail_id", sa.String(length=40), nullable=False),
        sa.Column("message_id", sa.String(length=40), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mail_id"], ["mail.mail_id"], name=op.f("fk_mail_message_mail_id_mail")
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["message.message_id"], name=op.f("fk_mail_message_message_id_message")
        ),
        sa.PrimaryKeyConstraint("mail_id", "message_id", name=op.f("pk_mail_message")),
    )
    op.create_table(
        "message_document",
        sa.Column("message_id", sa.String(length=40), nullable=False),
        sa.Column("document_id", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.document_id"],
            name=op.f("fk_message_document_document_id_document"),
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["message.message_id"],
            name=op.f("fk_message_document_message_id_message"),
        ),
        sa.PrimaryKeyConstraint("message_id", "document_id", name=op.f("pk_message_document")),
    )


def downgrade() -> None:
    op.drop_table("message_document")
    op.drop_table("mail_message")
    op.drop_table("message")
    op.drop_table("erp_record")
    with op.batch_alter_table("verdict", schema=None) as batch_op:
        batch_op.drop_index("ix_verdict_shipment")

    op.drop_table("verdict")
    with op.batch_alter_table("shipment_alias", schema=None) as batch_op:
        batch_op.drop_index("ix_shipment_alias_lookup")

    op.drop_table("shipment_alias")
    with op.batch_alter_table("observation", schema=None) as batch_op:
        batch_op.drop_index("ix_observation_projection")

    op.drop_table("observation")
    with op.batch_alter_table("mail", schema=None) as batch_op:
        batch_op.drop_index("ix_mail_sha256")

    op.drop_table("mail")
    op.drop_table("field_state")
    op.drop_table("erp_snapshot")
    op.drop_table("document")
