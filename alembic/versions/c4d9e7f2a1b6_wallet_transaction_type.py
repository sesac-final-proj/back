"""wallet_transactions: add type column (TRANSFER/QR_PAYMENT/CHARGE)

Revision ID: c4d9e7f2a1b6
Revises: b8f3a2c1d7e4
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d9e7f2a1b6"
down_revision: Union[str, None] = "b8f3a2c1d7e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallet_transactions",
        sa.Column("type", sa.String(length=20), nullable=False, server_default="TRANSFER"),
    )
    # 기존 QR 현장결제 행(store_id 있음)은 이미 TRANSFER로 채워졌을 테니 되짚어 정정.
    op.execute("UPDATE wallet_transactions SET type = 'QR_PAYMENT' WHERE store_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("wallet_transactions", "type")
