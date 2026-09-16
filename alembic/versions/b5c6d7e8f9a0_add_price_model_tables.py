"""add price_model_* tables (analyzer 가격예측 산출물 적재)

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("price_model_metrics"):
        op.create_table(
            "price_model_metrics",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("feature_set", sa.String(length=30), nullable=False),
            sa.Column("model_key", sa.String(length=30), nullable=False),
            sa.Column("label", sa.String(length=50), nullable=False),
            sa.Column("rmse", sa.Float(), nullable=False),
            sa.Column("mae", sa.Float(), nullable=False),
            sa.Column("mape", sa.Float(), nullable=False),
            sa.Column("r2", sa.Float(), nullable=False),
            sa.Column("hit10", sa.Float(), nullable=False),
            sa.Column("hit20", sa.Float(), nullable=False),
            sa.Column("extra", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not inspector.has_table("price_model_listings"):
        op.create_table(
            "price_model_listings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("detail_type", sa.String(length=50), nullable=False),
            sa.Column("gu", sa.String(length=50), nullable=False),
            sa.Column("condition", sa.String(length=30), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("chat_count", sa.Integer(), nullable=False),
            sa.Column("interest_count", sa.Integer(), nullable=False),
            sa.Column("view_count", sa.Float(), nullable=False),
            sa.Column("manner_temp", sa.Float(), nullable=False),
            sa.Column("title_length", sa.Integer(), nullable=False),
            sa.Column("days_since_listed", sa.Integer(), nullable=False),
            sa.Column("category_detail_median_price", sa.Float(), nullable=False),
            sa.Column("price", sa.Integer(), nullable=False),
            sa.Column("price_log", sa.Float(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
        )
        op.create_index("ix_price_model_listings_category", "price_model_listings", ["category"])

    if not inspector.has_table("price_predictions"):
        op.create_table(
            "price_predictions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("feature_set", sa.String(length=30), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("detail_type", sa.String(length=50), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("actual_price", sa.Integer(), nullable=False),
            sa.Column("predicted_price", sa.Integer(), nullable=False),
            sa.Column("error_rate", sa.Float(), nullable=False),
        )
        op.create_index("ix_price_predictions_feature_set", "price_predictions", ["feature_set"])

    if not inspector.has_table("price_platform_comparisons"):
        op.create_table(
            "price_platform_comparisons",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("platform", sa.String(length=30), nullable=False),
            sa.Column("sample_count", sa.Integer(), nullable=False),
            sa.Column("mean_price", sa.Float(), nullable=False),
            sa.Column("median_price", sa.Float(), nullable=False),
            sa.Column("std_price", sa.Float(), nullable=False),
            sa.Column("p25_price", sa.Float(), nullable=False),
            sa.Column("p75_price", sa.Float(), nullable=False),
        )
        op.create_index(
            "ix_price_platform_comparisons_category", "price_platform_comparisons", ["category"]
        )

    if not inspector.has_table("price_platform_tests"):
        op.create_table(
            "price_platform_tests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("platform_a", sa.String(length=30), nullable=False),
            sa.Column("platform_b", sa.String(length=30), nullable=False),
            sa.Column("median_a", sa.Float(), nullable=False),
            sa.Column("median_b", sa.Float(), nullable=False),
            sa.Column("diff_pct", sa.Float(), nullable=False),
            sa.Column("p_value", sa.Float(), nullable=False),
            sa.Column("significant", sa.Boolean(), nullable=False),
        )
        op.create_index("ix_price_platform_tests_category", "price_platform_tests", ["category"])

    if not inspector.has_table("price_clusters"):
        op.create_table(
            "price_clusters",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("price_band", sa.String(length=30), nullable=False),
            sa.Column("share", sa.Float(), nullable=False),
            sa.Column("median_price", sa.Float(), nullable=False),
            sa.Column("range_low", sa.Float(), nullable=False),
            sa.Column("range_high", sa.Float(), nullable=False),
            sa.Column("sample_count", sa.Integer(), nullable=False),
        )
        op.create_index("ix_price_clusters_category", "price_clusters", ["category"])


def downgrade() -> None:
    op.drop_table("price_clusters")
    op.drop_table("price_platform_tests")
    op.drop_table("price_platform_comparisons")
    op.drop_table("price_predictions")
    op.drop_table("price_model_listings")
    op.drop_table("price_model_metrics")
