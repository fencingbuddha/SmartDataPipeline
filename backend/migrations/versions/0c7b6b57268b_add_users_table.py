from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0c7b6b57268b"
down_revision = "20251104_0002"  # <-- keep this as in your history
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)  # unique via index (SQLite-friendly)
    # REMOVE: op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    # REMOVE: op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")