"""metric_daily: add value_distinct

Revision ID: 82993df14451
Revises: 443ef1cf2f58
Create Date: 2025-09-16 10:15:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "82993df14451"
down_revision: Union[str, Sequence[str], None] = "443ef1cf2f58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Notes:
    - On SQLite, ALTER TABLE cannot add constraints post-creation. The
      earlier revision 443ef1cf2f58 already defines a PRIMARY KEY on
      (metric_date, source_id, metric), so an additional unique constraint
      would be redundant anyway. We therefore only add the new column here.
    """
    # Add the new column using batch mode for SQLite compatibility.
    with op.batch_alter_table("metric_daily", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "value_distinct",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )

    # Optional: drop the server default now that existing rows are initialized.
    with op.batch_alter_table("metric_daily", schema=None) as batch_op:
        batch_op.alter_column("value_distinct", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("metric_daily", schema=None) as batch_op:
        batch_op.drop_column("value_distinct")
