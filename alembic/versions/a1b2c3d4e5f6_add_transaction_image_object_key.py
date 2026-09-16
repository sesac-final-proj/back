"""add transactions.image_object_key

Revision ID: a1b2c3d4e5f6
Revises: 960810a1e76a
Create Date: 2026-09-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '960810a1e76a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("transactions")}

    if "image_object_key" not in cols:
        op.add_column("transactions", sa.Column("image_object_key", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "image_object_key")
