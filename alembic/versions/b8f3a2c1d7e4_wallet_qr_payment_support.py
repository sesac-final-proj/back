"""wallet_transactions: support QR store payments

Revision ID: b8f3a2c1d7e4
Revises: 1254294de962
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8f3a2c1d7e4"
down_revision: Union[str, None] = "1254294de962"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("wallet_transactions", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "wallet_transactions_store_id_fkey", "wallet_transactions", "stores", ["store_id"], ["id"]
    )
    op.alter_column("wallet_transactions", "chat_room_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("wallet_transactions", "receiver_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("wallet_transactions", "receiver_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("wallet_transactions", "chat_room_id", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("wallet_transactions_store_id_fkey", "wallet_transactions", type_="foreignkey")
    op.drop_column("wallet_transactions", "store_id")
