"""Add the authenticated ReadyMode local worker queue."""

from alembic import op
import sqlalchemy as sa

revision = "0004_readymode_local_worker"
down_revision = "0003_readymode_dedupe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "readymode_worker_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("last_seen_at", sa.String(length=40), nullable=True),
    )
    op.create_table(
        "readymode_worker_jobs",
        sa.Column("job_id", sa.String(length=36), primary_key=True),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress_message", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("claim_token_hash", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'claimed', 'completed', 'failed')",
            name="readymode_worker_jobs_status_check",
        ),
    )
    op.create_index(
        "readymode_worker_jobs_queue_idx",
        "readymode_worker_jobs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("readymode_worker_jobs_queue_idx", table_name="readymode_worker_jobs")
    op.drop_table("readymode_worker_jobs")
    op.drop_table("readymode_worker_tokens")
