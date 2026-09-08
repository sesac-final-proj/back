"""add wallet_balance, wallet_transactions, chat_messages.payment_id

Revision ID: d3e4f5a6b7c8
Revises: c1f2a3b4d5e6
Create Date: 2026-09-08 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c1f2a3b4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 실제 계좌 연동 없는 mock 지갑 — 가입 시(및 기존 유저 백필) 초기 지급액.
INITIAL_WALLET_BALANCE = 100000


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "wallet_balance" not in user_cols:
        op.add_column(
            "users",
            sa.Column("wallet_balance", sa.Integer(), nullable=False, server_default=str(INITIAL_WALLET_BALANCE)),
        )

    if not inspector.has_table("wallet_transactions"):
        op.create_table(
            "wallet_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("chat_room_id", sa.Integer(), sa.ForeignKey("chat_rooms.id"), nullable=False),
            # 상품이 나중에 삭제돼도(trades/service.py delete_product) 송금 기록 자체는
            # 남겨야 해서 nullable — 삭제 시 참조만 끊는다(product_favorites와 달리 row를
            # 지우지 않음, ChatRoom.product_id와 동일 패턴).
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True),
            sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("receiver_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("balance_after", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_wallet_transactions_chat_room_id", "wallet_transactions", ["chat_room_id"])

    message_cols = {c["name"] for c in inspector.get_columns("chat_messages")}
    if "payment_id" not in message_cols:
        op.add_column(
            "chat_messages",
            sa.Column("payment_id", sa.Integer(), sa.ForeignKey("wallet_transactions.id"), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("chat_messages", "payment_id")
    op.drop_table("wallet_transactions")
    op.drop_column("users", "wallet_balance")
