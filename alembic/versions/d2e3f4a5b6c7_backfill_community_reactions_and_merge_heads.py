"""backfill community_post_comments/community_post_emotions + merge heads

이 DB엔 community_post_comments/community_post_emotions 테이블이 실제로 존재하는데
(app/models/community.py에 모델은 있음) 그 둘을 만든 마이그레이션 파일이 없었다 —
실제 DB introspect로 재구성한 backfill(신규 스키마 변경 없음).

겸사겸사 202609100001(admin_notices 계열, d6e7f8a9b0c1/202609090001로 이어짐)과
681a93484e95(trade place coordinates 계열)가 202609090001에서 각자 갈라진 채
병합 안 된 채로 남아있던 것도 여기서 합친다.

Revision ID: d2e3f4a5b6c7
Revises: 202609100001, 681a93484e95
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa


revision = "d2e3f4a5b6c7"
down_revision = ("202609100001", "681a93484e95")
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()

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
