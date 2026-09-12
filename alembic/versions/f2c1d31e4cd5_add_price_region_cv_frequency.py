"""add price_region_stats.cv_price/frequency_grade

어드민 "구별 통계" 표에 거래빈도 등급/가격 변동성을 구 단위로도 보여주기 위한
컬럼 — PriceCategorySummary의 같은 필드를 카테고리 전체가 아니라 (카테고리, 구)
단위로 계산한 것.

Revision ID: f2c1d31e4cd5
Revises: ac26ce0e5a10
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2c1d31e4cd5'
down_revision: Union[str, None] = 'ac26ce0e5a10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("price_region_stats")}
    if "cv_price" not in cols:
        op.add_column(
            "price_region_stats",
            sa.Column("cv_price", sa.Float(), nullable=False, server_default="0"),
        )
        op.alter_column("price_region_stats", "cv_price", server_default=None)
    if "frequency_grade" not in cols:
        op.add_column(
            "price_region_stats",
            sa.Column("frequency_grade", sa.String(length=10), nullable=False, server_default="C"),
        )
        op.alter_column("price_region_stats", "frequency_grade", server_default=None)


def downgrade() -> None:
    op.drop_column("price_region_stats", "frequency_grade")
    op.drop_column("price_region_stats", "cv_price")
