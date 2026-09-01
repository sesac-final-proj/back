"""register existing production auth schema baseline

Revision ID: a1c2e9f5b6d3
Revises: d4d0554591a5
Create Date: 2026-09-01 14:20:00.000000

"""
from typing import Sequence, Union


revision: str = "a1c2e9f5b6d3"
down_revision: Union[str, None] = "d4d0554591a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Production DB is already stamped with this revision and already contains
    # the auth/social baseline tables. Fresh local DBs continue in the next
    # revision, which creates missing tables defensively.
    pass


def downgrade() -> None:
    pass
