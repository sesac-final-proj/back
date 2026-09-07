"""add users.nickname_set/phone_number/phone_verified/profile_image_url

Revision ID: 2b4d11f439de
Revises: 41aa387cb1ca
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b4d11f439de'
down_revision: Union[str, None] = '41aa387cb1ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("nickname_set", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("phone_number", sa.String(length=20), nullable=True))
    op.add_column(
        "users",
        sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("profile_image_url", sa.String(length=500), nullable=True))
    op.create_unique_constraint("uq_users_phone_number", "users", ["phone_number"])
    # 기존 가입자는 소셜/이메일 가입 시점에 이미 자기 닉네임(정상 또는 임시)이 박혀있는
    # 상태라 nickname_set을 True로 소급 처리 — 새로 만든 플래그 때문에 기존 유저가
    # 다시 닉네임 설정 화면에 갇히는 걸 막는다.
    op.execute("UPDATE users SET nickname_set = true")


def downgrade() -> None:
    op.drop_constraint("uq_users_phone_number", "users", type_="unique")
    op.drop_column("users", "profile_image_url")
    op.drop_column("users", "phone_verified")
    op.drop_column("users", "phone_number")
    op.drop_column("users", "nickname_set")
