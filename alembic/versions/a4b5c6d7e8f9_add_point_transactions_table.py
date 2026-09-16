"""add point_transactions table (꿈방울 적립)

Revision ID: a4b5c6d7e8f9
Revises: f9a7b2c6d813
Create Date: 2026-09-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, None] = 'f9a7b2c6d813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("point_transactions"):
        op.create_table(
            "point_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=20), nullable=False),
            sa.Column("related_id", sa.Integer(), sa.ForeignKey("wallet_transactions.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_point_transactions_user_id", "point_transactions", ["user_id"])


def downgrade() -> None:
    op.drop_table("point_transactions")
