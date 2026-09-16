"""add community post management

Revision ID: 202609090001
Revises: a4b5c6d7e8f9
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa


revision = "202609090001"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("community_posts")}
    if "deleted_at" not in columns:
        op.add_column("community_posts", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    if "hidden_community_posts" not in inspector.get_table_names():
        op.create_table(
            "hidden_community_posts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "post_id", name="uq_hidden_community_posts_user_post"),
        )
        op.create_index("idx_hidden_community_posts_user_id", "hidden_community_posts", ["user_id"])


def downgrade():
    pass
