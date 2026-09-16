"""add price_listing_samples.interest_count

가격x관심수 산점도(어드민 "구별 가격 분포")용 — CSV 원본에 이미 있던 관심수 컬럼을
스웜 표본 테이블에도 같이 적재하기 위한 컬럼 추가.

Revision ID: d6028bb98ddf
Revises: 9cf30bbcbf00
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6028bb98ddf'
down_revision: Union[str, None] = '9cf30bbcbf00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("price_listing_samples")}
    if "interest_count" not in cols:
        op.add_column(
            "price_listing_samples",
            sa.Column("interest_count", sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column("price_listing_samples", "interest_count", server_default=None)


def downgrade() -> None:
    op.drop_column("price_listing_samples", "interest_count")
