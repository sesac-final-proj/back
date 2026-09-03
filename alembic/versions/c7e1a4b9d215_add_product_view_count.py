"""add products.view_count

Revision ID: c7e1a4b9d215
Revises: a3c2fe95fb03
Create Date: 2026-09-03 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e1a4b9d215'
down_revision: Union[str, None] = 'a3c2fe95fb03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("products", "view_count")
