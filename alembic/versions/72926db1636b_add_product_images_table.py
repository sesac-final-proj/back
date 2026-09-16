"""add product_images table

Revision ID: 72926db1636b
Revises: 43a608dbc4b9
Create Date: 2026-09-01 00:00:00.000000

staging에 먼저 합류한 736eeb896604가 이미 (호환되는 컬럼으로) product_images
테이블을 만든다 — 테이블 생성은 이미 있으면 건너뛰고, 거기 없던 인덱스만
계속 만들되 그것도 이미 있으면 건너뛴다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72926db1636b'
down_revision: Union[str, None] = '43a608dbc4b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "product_images" not in inspector.get_table_names():
        op.create_table(
            "product_images",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("object_key", sa.String(length=255), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    indexes = {i["name"] for i in inspector.get_indexes("product_images")}
    if "ix_product_images_product_id" not in indexes:
        op.create_index("ix_product_images_product_id", "product_images", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_product_images_product_id", table_name="product_images")
    op.drop_table("product_images")
