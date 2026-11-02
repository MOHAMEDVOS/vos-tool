"""Store short-lived encrypted payloads for ReadyMode worker tasks."""

from alembic import op
import sqlalchemy as sa

revision = "0005_readymode_worker_secrets"
down_revision = "0004_readymode_local_worker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "readymode_worker_job_secrets",
        sa.Column("job_id", sa.String(length=36), primary_key=True),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.String(length=40), nullable=False),
    )
    op.create_index(
        "readymode_worker_job_secrets_expiry_idx",
        "readymode_worker_job_secrets",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("readymode_worker_job_secrets_expiry_idx", table_name="readymode_worker_job_secrets")
    op.drop_table("readymode_worker_job_secrets")
