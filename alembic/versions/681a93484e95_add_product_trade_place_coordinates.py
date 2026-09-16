"""add product trade place coordinates

Revision ID: 681a93484e95
Revises: 202609090001
Create Date: 2026-09-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '681a93484e95'
down_revision: Union[str, None] = '202609090001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("products")}

    if "trade_place_lat" not in cols:
        op.add_column("products", sa.Column("trade_place_lat", sa.Numeric(9, 6), nullable=True))
    if "trade_place_lng" not in cols:
        op.add_column("products", sa.Column("trade_place_lng", sa.Numeric(9, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "trade_place_lng")
    op.drop_column("products", "trade_place_lat")
