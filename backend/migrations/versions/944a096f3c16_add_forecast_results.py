from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "944a096f3c16"
down_revision = "82993df14451"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "forecast_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("yhat", sa.Float(), nullable=False),
        sa.Column("yhat_lower", sa.Float(), nullable=True),
        sa.Column("yhat_upper", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=32), nullable=True),
    )
    op.create_unique_constraint(
        "uq_forecast_day", "forecast_results", ["source_id", "metric", "target_date"]
    )

def downgrade():
    op.drop_constraint("uq_forecast_day", "forecast_results", type_="unique")
    op.drop_table("forecast_results")
