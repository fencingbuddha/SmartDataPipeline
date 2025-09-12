"""Add metric_daily indexes

Revision ID: 97c813a0e571
Revises: beaed7f34243
Create Date: 2025-09-12 15:03:45.967636

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97c813a0e571'
down_revision: Union[str, Sequence[str], None] = 'beaed7f34243'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_metric_daily_date_source",
        "metric_daily",
        ["metric_date", "source_id"],
        unique=False,
    )
    op.create_index(
        "ix_metric_daily_metric",
        "metric_daily",
        ["metric"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_metric_daily_metric", table_name="metric_daily")
    op.drop_index("ix_metric_daily_date_source", table_name="metric_daily")

