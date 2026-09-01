"""add auth refresh/social tables and nickname unique

Revision ID: e61c9c1f2a10
Revises: d4d0554591a5
Create Date: 2026-09-01 10:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e61c9c1f2a10"
down_revision: Union[str, None] = "a1c2e9f5b6d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _names(items: list[dict]) -> set[str]:
    return {item["name"] for item in items if item.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    user_indexes = _names(inspector.get_indexes("users"))
    user_constraints = _names(inspector.get_unique_constraints("users"))
    if "ix_users_nickname" not in user_indexes and "users_nickname_key" not in user_constraints:
        op.create_index(op.f("ix_users_nickname"), "users", ["nickname"], unique=True)

    if "refresh_tokens" not in tables:
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token", sa.String(length=512), nullable=False),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token", name="refresh_tokens_token_key"),
        )
        op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)

    if "social_accounts" not in tables:
        op.create_table(
            "social_accounts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=20), nullable=False),
            sa.Column("provider_user_id", sa.String(length=100), nullable=False),
            sa.Column("access_token", sa.String(length=1024), nullable=True),
            sa.Column("refresh_token", sa.String(length=1024), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "provider_user_id", name="social_accounts_provider_provider_user_id_key"),
            sa.UniqueConstraint("user_id", "provider", name="social_accounts_user_id_provider_key"),
        )
        op.create_index("ix_social_accounts_user_id", "social_accounts", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "social_accounts" in tables:
        social_indexes = _names(inspector.get_indexes("social_accounts"))
        if "ix_social_accounts_user_id" in social_indexes:
            op.drop_index("ix_social_accounts_user_id", table_name="social_accounts")
        op.drop_table("social_accounts")

    if "refresh_tokens" in tables:
        refresh_indexes = _names(inspector.get_indexes("refresh_tokens"))
        if "idx_refresh_tokens_user_id" in refresh_indexes:
            op.drop_index("idx_refresh_tokens_user_id", table_name="refresh_tokens")
        op.drop_table("refresh_tokens")

    user_indexes = _names(inspector.get_indexes("users"))
    if "ix_users_nickname" in user_indexes:
        op.drop_index(op.f("ix_users_nickname"), table_name="users")
