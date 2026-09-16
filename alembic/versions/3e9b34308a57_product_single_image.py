"""product single image (image_object_key on products, drop product_images)

Revision ID: 3e9b34308a57
Revises: f86ff705aa40
Create Date: 2026-09-04 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e9b34308a57'
down_revision: Union[str, None] = 'f86ff705aa40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("products")}

    if "image_object_key" not in cols:
        op.add_column("products", sa.Column("image_object_key", sa.String(length=255), nullable=True))

    if inspector.has_table("product_images"):
        op.drop_table("product_images")


def downgrade() -> None:
    op.create_table(
        "product_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.drop_column("products", "image_object_key")
