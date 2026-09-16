"""add social account token metadata

Revision ID: f1b7d4a8c902
Revises: e61c9c1f2a10
Create Date: 2026-09-01 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1b7d4a8c902"
down_revision: Union[str, None] = "e61c9c1f2a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("social_accounts")}
    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("social_accounts")
        if constraint.get("name")
    }

    with op.batch_alter_table("social_accounts") as batch_op:
        if "token_expires_at" not in columns:
            batch_op.add_column(sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True))
        if "connected_at" not in columns:
            batch_op.add_column(
                sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
            )
        if "social_accounts_user_id_provider_key" not in constraints:
            batch_op.create_unique_constraint("social_accounts_user_id_provider_key", ["user_id", "provider"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("social_accounts")}
    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("social_accounts")
        if constraint.get("name")
    }

    with op.batch_alter_table("social_accounts") as batch_op:
        if "social_accounts_user_id_provider_key" in constraints:
            batch_op.drop_constraint("social_accounts_user_id_provider_key", type_="unique")
        if "connected_at" in columns:
            batch_op.drop_column("connected_at")
        if "token_expires_at" in columns:
            batch_op.drop_column("token_expires_at")
