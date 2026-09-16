"""add admin notices

Revision ID: 202609100001
Revises: d6e7f8a9b0c1
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa


revision = "202609100001"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "admin_notices" not in tables:
        op.create_table(
            "admin_notices",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("service", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("manual_status", sa.String(length=20), nullable=True),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
            sa.Column("alert_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("deleted_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["deleted_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_admin_notices_service", "admin_notices", ["service"])
        op.create_index("idx_admin_notices_deleted_order", "admin_notices", ["deleted_at", "display_order"])
    if "admin_notice_alerts" not in tables:
        op.create_table(
            "admin_notice_alerts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("notice_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["notice_id"], ["admin_notices.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("notice_id", "user_id", name="uq_admin_notice_alerts_notice_user"),
        )
        op.create_index("idx_admin_notice_alerts_notice_id", "admin_notice_alerts", ["notice_id"])
        op.create_index("idx_admin_notice_alerts_user_id", "admin_notice_alerts", ["user_id"])


def downgrade():
    pass
