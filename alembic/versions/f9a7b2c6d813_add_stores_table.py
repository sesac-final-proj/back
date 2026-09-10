"""add stores table (QR 현장결제 가맹점)

Revision ID: f9a7b2c6d813
Revises: d3e4f5a6b7c8
Create Date: 2026-09-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9a7b2c6d813'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("stores"):
        op.create_table(
            "stores",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        # 데모/테스트용 시드 — 실제 매장은 POST /api/v1/wallet/stores로 어드민이 등록.
        stores = sa.table("stores", sa.column("name", sa.String))
        op.bulk_insert(stores, [{"name": "당근카페"}])


def downgrade() -> None:
    op.drop_table("stores")
