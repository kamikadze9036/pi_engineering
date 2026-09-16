"""In-app bug reports, stored for later triage.

Revision ID: 0005_bug_reports
Revises: 0004_process_templates
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_bug_reports"
down_revision = "0004_process_templates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bug_reports",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), sa.Identity(), primary_key=True),
        sa.Column("reporter_id", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("page", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('OPEN','DONE')", name="bug_report_status"),
    )


def downgrade():
    op.drop_table("bug_reports")
