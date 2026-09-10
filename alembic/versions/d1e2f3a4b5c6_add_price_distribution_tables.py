"""add price_distribution_* tables (크롤링 분석 세션 어드민 지역비교 대시보드)

f8a9b0c1d2e3(price_model 계열)와 202609100001(admin_notices/community reactions
backfill 계열, 원래는 681a93484e95에서 이어짐)가 a4b5c6d7e8f9 이후로 각자 갈라진
채 병합 안 된 상태로 남아있던 걸 여기서 합친다(다른 스키마 변경 없이 head 두 개를
하나로 묶는 용도 겸용).

Revision ID: d1e2f3a4b5c6
Revises: f8a9b0c1d2e3, 202609100001
Create Date: 2026-09-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = ('f8a9b0c1d2e3', '202609100001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("price_category_summaries"):
        op.create_table(
            "price_category_summaries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("sample_count", sa.Integer(), nullable=False),
            sa.Column("median_price", sa.Float(), nullable=False),
            sa.Column("std_price", sa.Float(), nullable=False),
            sa.Column("cv_price", sa.Float(), nullable=False),
            sa.Column("price_trend_pct", sa.Float(), nullable=True),
            sa.Column("frequency_grade", sa.String(length=10), nullable=False),
            sa.Column("listings_per_month", sa.Float(), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            "ix_price_category_summaries_category",
            "price_category_summaries",
            ["category"],
            unique=True,
        )

    if not inspector.has_table("price_region_stats"):
        op.create_table(
            "price_region_stats",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("gu", sa.String(length=30), nullable=False),
            sa.Column("sample_count", sa.Integer(), nullable=False),
            sa.Column("median_price", sa.Float(), nullable=False),
            sa.Column("completion_rate", sa.Float(), nullable=False),
            sa.Column("avg_manner_temp", sa.Float(), nullable=False),
        )
        op.create_index("ix_price_region_stats_category", "price_region_stats", ["category"])

    if not inspector.has_table("price_detail_type_stats"):
        op.create_table(
            "price_detail_type_stats",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("detail_type", sa.String(length=50), nullable=False),
            sa.Column("gu", sa.String(length=30), nullable=False, server_default="전체"),
            sa.Column("sample_count", sa.Integer(), nullable=False),
            sa.Column("median_price", sa.Float(), nullable=False),
            sa.Column("cv_price", sa.Float(), nullable=False),
        )
        op.create_index(
            "ix_price_detail_type_stats_category", "price_detail_type_stats", ["category"]
        )

    if not inspector.has_table("price_listing_samples"):
        op.create_table(
            "price_listing_samples",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("gu", sa.String(length=30), nullable=False),
            sa.Column("price", sa.Integer(), nullable=False),
        )
        op.create_index(
            "ix_price_listing_samples_category", "price_listing_samples", ["category"]
        )

    if not inspector.has_table("price_dong_stats"):
        op.create_table(
            "price_dong_stats",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("gu", sa.String(length=30), nullable=False),
            sa.Column("dong", sa.String(length=30), nullable=False),
            sa.Column("sample_count", sa.Integer(), nullable=False),
            sa.Column("median_price", sa.Float(), nullable=False),
            sa.Column("within_pct", sa.Float(), nullable=False),
            sa.Column("below_pct", sa.Float(), nullable=False),
            sa.Column("above_pct", sa.Float(), nullable=False),
            sa.Column("dev_pct", sa.Float(), nullable=False),
        )
        op.create_index("ix_price_dong_stats_category", "price_dong_stats", ["category"])


def downgrade() -> None:
    op.drop_table("price_dong_stats")
    op.drop_table("price_listing_samples")
    op.drop_table("price_detail_type_stats")
    op.drop_table("price_region_stats")
    op.drop_table("price_category_summaries")
