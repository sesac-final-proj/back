"""add transactions and analysis tables

Revision ID: b0720884b58a
Revises: f1b7d4a8c902
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b0720884b58a'
down_revision: Union[str, None] = 'f1b7d4a8c902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_title", sa.String(length=200), nullable=False),
        sa.Column("search_keyword", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("detail_category", sa.String(length=50), nullable=True),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("region_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("trade_place", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("seller_nickname", sa.String(length=100), nullable=True),
        sa.Column("seller_manner_temp", sa.Numeric(4, 1), nullable=True),
        sa.Column("chat_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interest_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("listed_at", sa.Date(), nullable=False),
        sa.Column("traded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_transactions_region_category", "transactions", ["region_id", "category"])

    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_analyses_requested_by", "analyses", ["requested_by"])

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("price_min", sa.Integer(), nullable=True),
        sa.Column("price_max", sa.Integer(), nullable=True),
        sa.Column("frequency_grade", sa.String(length=10), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id"),
    )


def downgrade() -> None:
    op.drop_table("analysis_results")
    op.drop_index("idx_analyses_requested_by", table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("idx_transactions_region_category", table_name="transactions")
    op.drop_table("transactions")
