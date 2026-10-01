"""add job reliability and trip archive

Revision ID: 1f7c9a4b2d10
Revises: def206df1065
Create Date: 2026-10-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1f7c9a4b2d10"
down_revision: Union[str, Sequence[str], None] = "def206df1065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "planning_jobs",
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "planning_jobs",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_planning_jobs_attempts",
        "planning_jobs",
        "attempts >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_planning_jobs_attempts", "planning_jobs", type_="check")
    op.drop_column("planning_jobs", "heartbeat_at")
    op.drop_column("planning_jobs", "attempts")
    op.drop_column("trips", "archived_at")
