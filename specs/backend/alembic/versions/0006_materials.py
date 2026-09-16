"""Admin-managed list of used materials, for the Vstupní materiál dropdown.

Revision ID: 0006_materials
Revises: 0005_bug_reports
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_materials"
down_revision = "0005_bug_reports"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "materials",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("materials")
