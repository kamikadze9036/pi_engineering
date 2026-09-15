"""JSONB audit snapshots and immutable published template content.

Revision ID: 0003_jsonb_template_guard
Revises: 0002_pdf_templates
"""
from alembic import op

revision = "0003_jsonb_template_guard"
down_revision = "0002_pdf_templates"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
      ALTER TABLE audit_log ALTER COLUMN before_data TYPE jsonb USING before_data::jsonb;
      ALTER TABLE audit_log ALTER COLUMN after_data TYPE jsonb USING after_data::jsonb;
      CREATE OR REPLACE FUNCTION specs_guard_template() RETURNS trigger AS $$
      BEGIN
        IF TG_OP = 'DELETE' THEN
          RAISE EXCEPTION 'Published PDF templates cannot be deleted';
        END IF;
        IF OLD.version IS DISTINCT FROM NEW.version
           OR OLD.title IS DISTINCT FROM NEW.title
           OR OLD.settings::jsonb IS DISTINCT FROM NEW.settings::jsonb
           OR OLD.created_by IS DISTINCT FROM NEW.created_by THEN
          RAISE EXCEPTION 'Published PDF template content is immutable';
        END IF;
        RETURN NEW;
      END;
      $$ LANGUAGE plpgsql;
      CREATE TRIGGER guard_pdf_template BEFORE UPDATE OR DELETE ON pdf_templates
        FOR EACH ROW EXECUTE FUNCTION specs_guard_template();
    """)


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
      DROP TRIGGER IF EXISTS guard_pdf_template ON pdf_templates;
      DROP FUNCTION IF EXISTS specs_guard_template();
      ALTER TABLE audit_log ALTER COLUMN before_data TYPE json USING before_data::json;
      ALTER TABLE audit_log ALTER COLUMN after_data TYPE json USING after_data::json;
    """)
