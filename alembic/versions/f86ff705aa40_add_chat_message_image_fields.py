"""add chat message image fields

Revision ID: f86ff705aa40
Revises: 72926db1636b
Create Date: 2026-09-04 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f86ff705aa40'
down_revision: Union[str, None] = '72926db1636b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"]: c for c in inspector.get_columns("chat_messages")}

    if "message_type" not in cols:
        op.add_column(
            "chat_messages",
            sa.Column("message_type", sa.String(length=10), nullable=False, server_default="TEXT"),
        )
    if "image_object_key" not in cols:
        op.add_column("chat_messages", sa.Column("image_object_key", sa.String(length=255), nullable=True))
    if "content" in cols and not cols["content"]["nullable"]:
        op.alter_column("chat_messages", "content", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("chat_messages", "content", existing_type=sa.Text(), nullable=False)
    op.drop_column("chat_messages", "image_object_key")
    op.drop_column("chat_messages", "message_type")
