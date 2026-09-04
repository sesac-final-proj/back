"""add products.seller_manner_temp

Revision ID: a3c2fe95fb03
Revises: 5641ea6aa013
Create Date: 2026-09-03 00:00:00.000000

staging에 먼저 합류한 736eeb896604가 products 테이블을 만들 때 이미 이
컬럼을 포함해서 만든다 — 이미 있으면 건너뛰는 방어 코드로 바꿔서 어느
순서로 적용되든 안전하게.
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
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("products")}
    if "seller_manner_temp" not in columns:
        op.add_column("products", sa.Column("seller_manner_temp", sa.Numeric(4, 1), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "seller_manner_temp")
