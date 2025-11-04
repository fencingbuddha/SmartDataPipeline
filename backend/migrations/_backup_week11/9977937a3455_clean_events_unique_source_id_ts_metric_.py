"""clean_events unique (source_id, ts, metric) + indexes

Revision ID: 9977937a3455
Revises: 3d35f200e596
Create Date: 2025-09-17 10:56:44.515376

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9977937a3455'
down_revision: Union[str, Sequence[str], None] = '3d35f200e596'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing_uc = {uc["name"] for uc in insp.get_unique_constraints("clean_events")}
    existing_ix = {ix["name"] for ix in insp.get_indexes("clean_events")}

    if "uq_clean_events_src_ts_metric" not in existing_uc:
        op.create_unique_constraint(
            "uq_clean_events_src_ts_metric",
            "clean_events",
            ["source_id", "ts", "metric"],
        )

    if "ix_clean_events_ts" not in existing_ix:
        op.create_index("ix_clean_events_ts", "clean_events", ["ts"])

    if "ix_clean_events_source_id" not in existing_ix:
        op.create_index("ix_clean_events_source_id", "clean_events", ["source_id"])

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing_uc = {uc["name"] for uc in insp.get_unique_constraints("clean_events")}
    existing_ix = {ix["name"] for ix in insp.get_indexes("clean_events")}

    if "ix_clean_events_source_id" in existing_ix:
        op.drop_index("ix_clean_events_source_id", table_name="clean_events")

    if "ix_clean_events_ts" in existing_ix:
        op.drop_index("ix_clean_events_ts", table_name="clean_events")

    if "uq_clean_events_src_ts_metric" in existing_uc:
        op.drop_constraint(
            "uq_clean_events_src_ts_metric",
            "clean_events",
            type_="unique",
        )
