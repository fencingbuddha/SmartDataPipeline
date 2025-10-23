"""add forecast_models table

Revision ID: 175be0bb8ec7
Revises: 944a096f3c16
Create Date: 2025-10-23 16:03:33.467525
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "175be0bb8ec7"
down_revision: Union[str, Sequence[str], None] = "944a096f3c16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create forecast_models and supporting index."""
    op.create_table(
        "forecast_models",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer,
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(length=128), nullable=False),
        sa.Column(
            "model_name",
            sa.String(length=64),
            nullable=False,
            server_default="SARIMAX",
        ),
        sa.Column(
            "model_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("window_n", sa.Integer, nullable=False),
        sa.Column(
            "horizon_n",
            sa.Integer,
            nullable=False,
            server_default="7",
        ),
        sa.Column(
            "trained_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("train_start", sa.Date(), nullable=True),
        sa.Column("train_end", sa.Date(), nullable=True),
        sa.Column("mape", sa.Float, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.UniqueConstraint(
            "source_id",
            "metric",
            "window_n",
            name="uq_forecast_models_source_metric_window",
        ),
    )

    op.create_index(
        "ix_forecast_models_source_metric_window",
        "forecast_models",
        ["source_id", "metric", "window_n"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema: drop index and table."""
    op.drop_index(
        "ix_forecast_models_source_metric_window",
        table_name="forecast_models",
    )
    op.drop_table("forecast_models")
