"""Reusable starting templates for new specifications.

Revision ID: 0004_process_templates
Revises: 0003_jsonb_template_guard
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0004_process_templates"
down_revision = "0003_jsonb_template_guard"
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "process_templates",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_revision_id", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  sa.ForeignKey("process_spec_revisions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
          CREATE OR REPLACE FUNCTION specs_guard_process_template() RETURNS trigger AS $$
          BEGIN
            IF TG_OP = 'DELETE' THEN
              RAISE EXCEPTION 'Process templates cannot be deleted';
            END IF;
            IF OLD.name IS DISTINCT FROM NEW.name
               OR OLD.description IS DISTINCT FROM NEW.description
               OR OLD.source_revision_id IS DISTINCT FROM NEW.source_revision_id
               OR OLD.payload IS DISTINCT FROM NEW.payload
               OR OLD.is_system IS DISTINCT FROM NEW.is_system
               OR OLD.created_by IS DISTINCT FROM NEW.created_by THEN
              RAISE EXCEPTION 'Process template content is immutable';
            END IF;
            RETURN NEW;
          END;
          $$ LANGUAGE plpgsql;
          CREATE TRIGGER guard_process_template BEFORE UPDATE OR DELETE ON process_templates
            FOR EACH ROW EXECUTE FUNCTION specs_guard_process_template();
        """)


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS guard_process_template ON process_templates")
        op.execute("DROP FUNCTION IF EXISTS specs_guard_process_template()")
    op.drop_table("process_templates")
