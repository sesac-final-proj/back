"""add region_id to point_transactions

Revision ID: 1254294de962
Revises: ae1c8596bbac
Create Date: 2026-09-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1254294de962'
down_revision: Union[str, None] = 'ae1c8596bbac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("point_transactions", sa.Column("region_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_point_transactions_region_id", "point_transactions", "regions", ["region_id"], ["id"]
    )
    op.create_index("ix_point_transactions_region_id", "point_transactions", ["region_id"])


def downgrade() -> None:
    op.drop_index("ix_point_transactions_region_id", table_name="point_transactions")
    op.drop_constraint("fk_point_transactions_region_id", "point_transactions", type_="foreignkey")
    op.drop_column("point_transactions", "region_id")
