"""add products.description

Revision ID: 5641ea6aa013
Revises: b0720884b58a
Create Date: 2026-09-03 00:00:00.000000

staging에 먼저 합류한 736eeb896604가 products 테이블을 만들 때 이미 이
컬럼을 포함해서 만든다 — 이미 있으면 건너뛰는 방어 코드로 바꿔서 어느
순서로 적용되든 안전하게.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5641ea6aa013'
down_revision: Union[str, None] = 'b0720884b58a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("products")}
    if "description" not in columns:
        op.add_column("products", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "description")
