"""register remaining existing tables (dream/local/community/admin + trades)

Revision ID: 736eeb896604
Revises: f1b7d4a8c902
Create Date: 2026-09-03 00:00:00.000000

DB의 alembic_version이 이 저장소에 없는 리비전(43a608dbc4b9)을 가리키고
있었다 — 우리 마이그레이션 체인 밖에서 만들어진 테이블이 많다는 뜻.
아래 테이블들은 이미 운영 DB에 존재하지만 어떤 마이그레이션에도 기록돼
있지 않았다: products, chat_rooms, chat_room_participants, product_images,
transactions, analyses, analysis_results, facilities, point_accounts,
point_transactions, donation_settings, donations, fundraising_goals,
merchant_spends, community_posts, comments, post_reactions, local_notices,
alerts, collection_errors, nuri_crawled, parking.

기존 DB엔 `IF NOT EXISTS`처럼 존재 여부 확인 후 생성(e61c9c1f2a10과 동일한
패턴)해서 안전하게 만들고, 이 리비전으로 stamp해서 alembic_version을
우리 체인 안으로 되돌린다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "736eeb896604"
down_revision: Union[str, None] = "f1b7d4a8c902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "products" not in tables:
        op.create_table(
            "products",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("detail_category", sa.String(length=50), nullable=True),
            sa.Column("search_keyword", sa.String(length=100), nullable=True),
            sa.Column("desired_price", sa.Integer(), nullable=True),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("trade_status", sa.String(length=20), nullable=False, server_default="SALE"),
            sa.Column("trade_type", sa.String(length=20), nullable=False, server_default="SALE"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("trade_place", sa.String(length=200), nullable=True),
            sa.Column("seller_nickname", sa.String(length=100), nullable=True),
            sa.Column("seller_manner_temp", sa.Numeric(), nullable=True),
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("interest_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "chat_rooms" not in tables:
        op.create_table(
            "chat_rooms",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=True),
            sa.Column("last_message", sa.String(length=500), nullable=True),
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "chat_room_participants" not in tables:
        op.create_table(
            "chat_room_participants",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("chat_room_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["chat_room_id"], ["chat_rooms.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "product_images" not in tables:
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

    if "transactions" not in tables:
        op.create_table(
            "transactions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("product_title", sa.String(length=200), nullable=False),
            sa.Column("search_keyword", sa.String(length=100), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("detail_category", sa.String(length=50), nullable=True),
            sa.Column("price", sa.Integer(), nullable=True),
            sa.Column("region_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("trade_place", sa.String(length=200), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("seller_nickname", sa.String(length=100), nullable=True),
            sa.Column("seller_manner_temp", sa.Numeric(precision=4, scale=1), nullable=True),
            sa.Column("chat_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("interest_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("listed_at", sa.Date(), nullable=False),
            sa.Column("traded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "analyses" not in tables:
        op.create_table(
            "analyses",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("requested_by", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "analysis_results" not in tables:
        op.create_table(
            "analysis_results",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("analysis_id", sa.Integer(), nullable=False),
            sa.Column("price_min", sa.Integer(), nullable=True),
            sa.Column("price_max", sa.Integer(), nullable=True),
            sa.Column("frequency_grade", sa.String(length=10), nullable=False),
            sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("evidence_json", sa.JSON(), nullable=True),
            sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("analysis_id", name="analysis_results_analysis_id_key"),
        )

    if "facilities" not in tables:
        op.create_table(
            "facilities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("facility_type", sa.String(length=30), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("lat", sa.Float(), nullable=True),
            sa.Column("lng", sa.Float(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "point_accounts" not in tables:
        op.create_table(
            "point_accounts",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("user_id"),
        )

    if "point_transactions" not in tables:
        op.create_table(
            "point_transactions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=20), nullable=False),
            sa.Column("related_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "donation_settings" not in tables:
        op.create_table(
            "donation_settings",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("donation_rate", sa.Integer(), nullable=False),
            sa.Column("facility_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"]),
            sa.PrimaryKeyConstraint("user_id"),
        )

    if "donations" not in tables:
        op.create_table(
            "donations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("facility_id", sa.Integer(), nullable=False),
            sa.Column("point_transaction_id", sa.Integer(), nullable=True),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"]),
            sa.ForeignKeyConstraint(["point_transaction_id"], ["point_transactions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "fundraising_goals" not in tables:
        op.create_table(
            "fundraising_goals",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("facility_id", sa.Integer(), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("target_amount", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "facility_id", "period_start", name="fundraising_goals_facility_id_period_start_key"
            ),
        )

    if "merchant_spends" not in tables:
        op.create_table(
            "merchant_spends",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("facility_id", sa.Integer(), nullable=True),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("merchant_name", sa.String(length=100), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("spent_at", sa.Date(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"]),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "community_posts" not in tables:
        op.create_table(
            "community_posts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("category", sa.String(length=30), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("emotion_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "comments" not in tables:
        op.create_table(
            "comments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("parent_comment_id", sa.Integer(), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["parent_comment_id"], ["comments.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "post_reactions" not in tables:
        op.create_table(
            "post_reactions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("post_id", "user_id", name="post_reactions_post_id_user_id_key"),
        )

    if "local_notices" not in tables:
        op.create_table(
            "local_notices",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=20), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("raw_content", sa.Text(), nullable=False),
            sa.Column("summary_json", sa.JSON(), nullable=True),
            sa.Column("lat", sa.Float(), nullable=True),
            sa.Column("lng", sa.Float(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("dedup_group_id", sa.String(length=64), nullable=True),
            sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "alerts" not in tables:
        op.create_table(
            "alerts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("notice_id", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["notice_id"], ["local_notices.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "collection_errors" not in tables:
        op.create_table(
            "collection_errors",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=20), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "nuri_crawled" not in tables:
        op.create_table(
            "nuri_crawled",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("source", sa.Text(), nullable=False, server_default="nuri"),
            sa.Column("external_id", sa.Text(), nullable=False),
            sa.Column("risk_type", sa.Text(), nullable=False),
            sa.Column("risk_name", sa.Text(), nullable=True),
            sa.Column("risk_level", sa.Text(), nullable=True),
            sa.Column("risk_score", sa.Numeric(), nullable=True),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("sido", sa.Text(), nullable=True),
            sa.Column("sigungu", sa.Text(), nullable=True),
            sa.Column("dong", sa.Text(), nullable=True),
            sa.Column("latitude", sa.Float(), nullable=True),
            sa.Column("longitude", sa.Float(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("crawled_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("source_url", sa.Text(), nullable=True),
            sa.Column("raw_data", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source", "external_id", name="nuri_crawled_source_external_id_key"),
        )

    if "parking" not in tables:
        op.create_table(
            "parking",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table in [
        "parking",
        "nuri_crawled",
        "collection_errors",
        "alerts",
        "local_notices",
        "post_reactions",
        "comments",
        "community_posts",
        "merchant_spends",
        "fundraising_goals",
        "donations",
        "donation_settings",
        "point_transactions",
        "point_accounts",
        "facilities",
        "analysis_results",
        "analyses",
        "transactions",
        "product_images",
        "chat_room_participants",
        "chat_rooms",
        "products",
    ]:
        if table in tables:
            op.drop_table(table)
