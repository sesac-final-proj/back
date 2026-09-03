"""add products.seller_manner_temp

Revision ID: a3c2fe95fb03
Revises: 5641ea6aa013
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c2fe95fb03'
down_revision: Union[str, None] = '5641ea6aa013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("seller_manner_temp", sa.Numeric(4, 1), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "seller_manner_temp")
