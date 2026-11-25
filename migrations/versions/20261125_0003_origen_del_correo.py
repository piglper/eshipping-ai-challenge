"""Origen de cada correo y orden de los incrustados (F4.2).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-25 10:05:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mail", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_ref", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("position", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("mail", schema=None) as batch_op:
        batch_op.drop_column("position")
        batch_op.drop_column("source_ref")
