"""add audit_logs table

Revision ID: 0001_add_audit_logs
Revises:
Create Date: 2026-04-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_add_audit_logs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admins.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("idx_audit_log_admin", "audit_logs", ["admin_id", "created_at"])
    op.create_index("idx_audit_log_target", "audit_logs", ["target_type", "target_id"])
    op.create_index("idx_audit_log_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_index("idx_audit_log_action", table_name="audit_logs")
    op.drop_index("idx_audit_log_target", table_name="audit_logs")
    op.drop_index("idx_audit_log_admin", table_name="audit_logs")
    op.drop_table("audit_logs")
