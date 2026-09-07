"""add user_regions table (multi-region)

Revision ID: b2c3d4e5f607
Revises: a1b2c3d4e5f6
Create Date: 2026-09-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f607'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("user_regions"):
        op.create_table(
            "user_regions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=False),
            sa.Column("radius_m", sa.Integer(), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "region_id", name="user_regions_user_id_region_id_key"),
        )
        op.create_index("ix_user_regions_user_id", "user_regions", ["user_id"])

    # 백필: 기존 users.region_id가 있는 유저는 그 값을 primary user_regions 행 1개로 복사.
    # radius_m은 NOT NULL이라 비어있으면 1000m(기본 거래반경)로 채운다.
    bind.execute(
        sa.text(
            """
            INSERT INTO user_regions (user_id, region_id, radius_m, is_primary)
            SELECT id, region_id, COALESCE(radius_m, 1000), true
            FROM users
            WHERE region_id IS NOT NULL
            ON CONFLICT (user_id, region_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_table("user_regions")
