"""drop users.phone_verified

전화번호 인증(OTP/알림톡) 로직을 뺐다 — 번호는 그냥 수집만 하므로
"인증됨" 플래그가 의미가 없어져서 제거.

Revision ID: 5977a60cd3ba
Revises: 2b4d11f439de
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5977a60cd3ba'
down_revision: Union[str, None] = '2b4d11f439de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "phone_verified")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
