"""backfill admin_notices/admin_notice_alerts/community_post_comments/community_post_emotions

DB의 alembic_version이 이미 '202609100001'을 가리키고 있는데(원격 개발 DB에 이 4개
테이블이 실제로 존재) 이 리비전을 만든 원본 마이그레이션 파일이 저장소 어디에도
없었다 — 커밋/push 없이 로컬에서만 적용되고 파일이 유실된 것으로 보임. 실제 DB를
그대로 introspect해서 여기 재구성한다(신규 스키마 변경 없음, 순수 backfill).

Revision ID: 202609100001
Revises: 681a93484e95
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa


revision = "202609100001"
down_revision = "681a93484e95"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()

    if "admin_notices" not in existing:
        op.create_table(
            "admin_notices",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("service", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("manual_status", sa.String(length=20), nullable=True),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("alert_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("deleted_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="admin_notices_created_by_fkey"),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="admin_notices_updated_by_fkey"),
            sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], name="admin_notices_deleted_by_fkey"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_admin_notices_service", "admin_notices", ["service"])
        op.create_index("idx_admin_notices_deleted_order", "admin_notices", ["deleted_at", "display_order"])

    if "admin_notice_alerts" not in existing:
        op.create_table(
            "admin_notice_alerts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("notice_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["notice_id"], ["admin_notices.id"], name="admin_notice_alerts_notice_id_fkey"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="admin_notice_alerts_user_id_fkey"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("notice_id", "user_id", name="uq_admin_notice_alerts_notice_user"),
        )
        op.create_index("idx_admin_notice_alerts_notice_id", "admin_notice_alerts", ["notice_id"])
        op.create_index("idx_admin_notice_alerts_user_id", "admin_notice_alerts", ["user_id"])

    if "community_post_comments" not in existing:
        op.create_table(
            "community_post_comments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"], name="fk_community_post_comments_post_id"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_community_post_comments_user_id"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_community_post_comments_post_id", "community_post_comments", ["post_id"])
        op.create_index("ix_community_post_comments_user_id", "community_post_comments", ["user_id"])

    if "community_post_emotions" not in existing:
        op.create_table(
            "community_post_emotions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"], name="fk_community_post_emotions_post_id"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_community_post_emotions_user_id"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "post_id", name="uq_community_post_emotions_user_post"),
        )
        op.create_index("ix_community_post_emotions_post_id", "community_post_emotions", ["post_id"])
        op.create_index("ix_community_post_emotions_user_id", "community_post_emotions", ["user_id"])


def downgrade():
    op.drop_table("community_post_emotions")
    op.drop_table("community_post_comments")
    op.drop_table("admin_notice_alerts")
    op.drop_table("admin_notices")
