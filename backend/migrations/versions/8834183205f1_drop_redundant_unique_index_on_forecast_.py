"""drop redundant unique index on forecast_models

Revision ID: 8834183205f1
Revises: 175be0bb8ec7
Create Date: 2025-10-23 16:54:45.546110
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8834183205f1"
down_revision: Union[str, Sequence[str], None] = "175be0bb8ec7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: drop redundant unique index, keep the UC."""
    op.drop_index("ix_forecast_models_source_metric_window", table_name="forecast_models")


def downgrade() -> None:
    """Downgrade schema: restore the unique index."""
    op.create_index(
        "ix_forecast_models_source_metric_window",
        "forecast_models",
        ["source_id", "metric", "window_n"],
        unique=True,
    )
