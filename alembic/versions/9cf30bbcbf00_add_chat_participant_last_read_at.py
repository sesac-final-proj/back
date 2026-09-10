"""add chat_room_participants.last_read_at

카톡식 "상대가 읽었는지" 표시(내가 보낸 메시지 옆 1)를 위한 컬럼 — 참여자가
메시지함을 마지막으로 연 시각을 저장한다.

Revision ID: 9cf30bbcbf00
Revises: d1e2f3a4b5c6
Create Date: 2026-09-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9cf30bbcbf00'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("chat_room_participants")}
    if "last_read_at" not in cols:
        op.add_column(
            "chat_room_participants",
            sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("chat_room_participants", "last_read_at")
