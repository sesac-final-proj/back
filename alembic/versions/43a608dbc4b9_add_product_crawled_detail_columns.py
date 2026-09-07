"""add products.detail_category/trade_place/seller_nickname/interest_count

Revision ID: 43a608dbc4b9
Revises: c7e1a4b9d215
Create Date: 2026-09-03 12:00:00.000000

staging에 먼저 합류한 736eeb896604가 products 테이블을 만들 때 이미 이
컬럼들을 포함해서 만든다 — 이미 있으면 건너뛰는 방어 코드로 바꿔서 어느
순서로 적용되든 안전하게.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43a608dbc4b9'
down_revision: Union[str, None] = 'c7e1a4b9d215'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("products")}
    if "detail_category" not in columns:
        op.add_column("products", sa.Column("detail_category", sa.String(length=50), nullable=True))
    if "trade_place" not in columns:
        op.add_column("products", sa.Column("trade_place", sa.String(length=200), nullable=True))
    if "seller_nickname" not in columns:
        op.add_column("products", sa.Column("seller_nickname", sa.String(length=100), nullable=True))
    if "interest_count" not in columns:
        op.add_column("products", sa.Column("interest_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("products", "interest_count")
    op.drop_column("products", "seller_nickname")
    op.drop_column("products", "trade_place")
    op.drop_column("products", "detail_category")
