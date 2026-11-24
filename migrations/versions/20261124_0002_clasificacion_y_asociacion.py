"""Clasificación y asociación de los mensajes (F3.5).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24 19:36:23.394285
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "association",
        sa.Column("message_id", sa.String(length=40), nullable=False),
        sa.Column("shipment_id", sa.String(length=40), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"], ["message.message_id"], name=op.f("fk_association_message_id_message")
        ),
        sa.PrimaryKeyConstraint("message_id", "shipment_id", name=op.f("pk_association")),
    )
    with op.batch_alter_table("association", schema=None) as batch_op:
        batch_op.create_index("ix_association_shipment", ["shipment_id"], unique=False)

    op.create_table(
        "classification",
        sa.Column("message_id", sa.String(length=40), nullable=False),
        sa.Column("mail_class", sa.String(length=8), nullable=False),
        sa.Column("extractor_version", sa.String(length=40), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["message.message_id"],
            name=op.f("fk_classification_message_id_message"),
        ),
        sa.PrimaryKeyConstraint(
            "message_id", "mail_class", "extractor_version", name=op.f("pk_classification")
        ),
    )


def downgrade() -> None:
    op.drop_table("classification")
    with op.batch_alter_table("association", schema=None) as batch_op:
        batch_op.drop_index("ix_association_shipment")

    op.drop_table("association")
