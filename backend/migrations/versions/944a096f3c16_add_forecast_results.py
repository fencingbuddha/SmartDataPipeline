from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "944a096f3c16"
down_revision = "82993df14451"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    table_name = "forecast_results"
    uc_name = "uq_forecast_day"

    existing_tables = set(insp.get_table_names())
    if table_name not in existing_tables:
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("metric", sa.String(length=64), nullable=False),
            sa.Column("target_date", sa.Date(), nullable=False),
            sa.Column("yhat", sa.Float(), nullable=False),
            sa.Column("yhat_lower", sa.Float(), nullable=True),
            sa.Column("yhat_upper", sa.Float(), nullable=True),
            sa.Column("model_version", sa.String(length=32), nullable=True),
        )

    # (Re)check unique constraints and create only if missing
    existing_ucs = {uc["name"] for uc in insp.get_unique_constraints(table_name)}
    if uc_name not in existing_ucs:
        op.create_unique_constraint(uc_name, table_name, ["source_id", "metric", "target_date"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    table_name = "forecast_results"
    uc_name = "uq_forecast_day"

    existing_tables = set(insp.get_table_names())
    if table_name in existing_tables:
        existing_ucs = {uc["name"] for uc in insp.get_unique_constraints(table_name)}
        if uc_name in existing_ucs:
            op.drop_constraint(uc_name, table_name, type_="unique")
        op.drop_table(table_name)
