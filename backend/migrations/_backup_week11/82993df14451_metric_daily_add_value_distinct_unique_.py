"""metric_daily: add value_distinct + unique idx

Revision ID: 82993df14451
Revises: 443ef1cf2f58
Create Date: 2025-09-22 13:48:02.934098

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82993df14451'
down_revision: Union[str, Sequence[str], None] = '443ef1cf2f58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("metric_daily", sa.Column("value_distinct", sa.Integer(), nullable=True))
    op.create_unique_constraint(
        "uq_metric_daily_day_src_metric",
        "metric_daily",
        ["metric_date", "source_id", "metric"],
    )

def downgrade():
    op.drop_constraint("uq_metric_daily_day_src_metric", "metric_daily", type_="unique")
    op.drop_column("metric_daily", "value_distinct")

