# alembic/versions/<rev>_create_metric_daily.py
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "443ef1cf2f58"
down_revision = "9977937a3455"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "metric_daily",
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("value_sum", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("value_avg", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("value_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("metric_date", "source_id", "metric", name="pk_metric_daily"),
    )

    op.create_index("ix_metric_daily_source_date", "metric_daily", ["source_id", "metric_date"])
    op.create_index("ix_metric_daily_metric_date", "metric_daily", ["metric", "metric_date"])

def downgrade():
    op.drop_index("ix_metric_daily_metric_date", table_name="metric_daily")
    op.drop_index("ix_metric_daily_source_date", table_name="metric_daily")
    op.drop_table("metric_daily")
