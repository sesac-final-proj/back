"""add image_object_key to stores

Revision ID: ae1c8596bbac
Revises: f2c1d31e4cd5
Create Date: 2026-09-12 21:06:37.179490
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ae1c8596bbac'
down_revision: Union[str, None] = 'f2c1d31e4cd5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("image_object_key", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("stores", "image_object_key")
