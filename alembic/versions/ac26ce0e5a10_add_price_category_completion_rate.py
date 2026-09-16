"""add price_category_summaries.completion_rate

어드민 "가격 지역별 비교" 상단 카드에 카테고리 전체 완료율(%)을 추가로 보여주기
위한 컬럼 — PriceRegionStat.completion_rate와 같은 계산을 카테고리 전체로 한 것.

Revision ID: ac26ce0e5a10
Revises: d6028bb98ddf
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac26ce0e5a10'
down_revision: Union[str, None] = 'd6028bb98ddf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("price_category_summaries")}
    if "completion_rate" not in cols:
        op.add_column(
            "price_category_summaries",
            sa.Column("completion_rate", sa.Float(), nullable=False, server_default="0"),
        )
        op.alter_column("price_category_summaries", "completion_rate", server_default=None)


def downgrade() -> None:
    op.drop_column("price_category_summaries", "completion_rate")
