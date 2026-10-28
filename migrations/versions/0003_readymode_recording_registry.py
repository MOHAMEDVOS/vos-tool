"""Track ReadyMode recordings by their stable source ID."""

from alembic import op
import sqlalchemy as sa

revision = "0003_readymode_dedupe"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "readymode_recordings",
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("dialer_host", sa.String(length=255), nullable=False),
        sa.Column("recording_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'failed', 'audited')",
            name="readymode_recordings_status_check",
        ),
        sa.PrimaryKeyConstraint(
            "username",
            "dialer_host",
            "recording_id",
            name="readymode_recordings_pkey",
        ),
    )


def downgrade() -> None:
    op.drop_table("readymode_recordings")
