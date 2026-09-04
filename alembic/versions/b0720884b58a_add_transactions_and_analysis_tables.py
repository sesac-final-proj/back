"""add transactions and analysis tables

Revision ID: b0720884b58a
Revises: 5977a60cd3ba
Create Date: 2026-09-01 00:00:00.000000

이 마이그레이션이 만들던 transactions/analyses/analysis_results 테이블은
staging에 먼저 합류한 736eeb896604(register_remaining_existing_tables)가
이미 (호환되는 컬럼으로) 만들어서 테이블 생성 부분은 그대로 두면 "relation
already exists"로 깨진다 — a1c2e9f5b6d3(existing_production_auth_schema)와
같은 이유로 no-op 처리. 인덱스 2개는 736eeb896604에 없어서 여기서 계속
만들되, 이미 있으면 건너뛴다(신규 DB든 이미 적용된 공용 dev DB든 안전).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0720884b58a'
down_revision: Union[str, None] = '5977a60cd3ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    transactions_indexes = {i["name"] for i in inspector.get_indexes("transactions")}
    if "idx_transactions_region_category" not in transactions_indexes:
        op.create_index("idx_transactions_region_category", "transactions", ["region_id", "category"])

    analyses_indexes = {i["name"] for i in inspector.get_indexes("analyses")}
    if "idx_analyses_requested_by" not in analyses_indexes:
        op.create_index("idx_analyses_requested_by", "analyses", ["requested_by"])


def downgrade() -> None:
    op.drop_index("idx_analyses_requested_by", table_name="analyses")
    op.drop_index("idx_transactions_region_category", table_name="transactions")
