"""add price_feature_importances table

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-09-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6d7e8f9a0b1'
down_revision: Union[str, None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("price_feature_importances"):
        op.create_table(
            "price_feature_importances",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("feature_set", sa.String(length=30), nullable=False),
            sa.Column("feature", sa.String(length=100), nullable=False),
            sa.Column("gain", sa.Float(), nullable=False),
            sa.Column("split", sa.Integer(), nullable=False),
        )
        op.create_index(
            "ix_price_feature_importances_feature_set", "price_feature_importances", ["feature_set"]
        )


def downgrade() -> None:
    op.drop_table("price_feature_importances")
