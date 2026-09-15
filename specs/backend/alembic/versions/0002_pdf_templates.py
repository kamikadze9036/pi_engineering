"""Versioned PDF layout settings.

Revision ID: 0002_pdf_templates
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_pdf_templates"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pdf_templates",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), sa.Identity(), primary_key=True),
        sa.Column("version", sa.String(40), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("pdf_templates")
