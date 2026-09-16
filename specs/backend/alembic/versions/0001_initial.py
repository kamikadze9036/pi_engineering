"""MVP tables and PostgreSQL immutability guards.

Revision ID: 0001_initial
Revises:
"""
from alembic import op

from app.database import Base
from app import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    initial_tables = [table for table in Base.metadata.sorted_tables
                      if table.name not in {"pdf_templates", "process_templates"}]
    Base.metadata.create_all(bind=bind, tables=initial_tables)
    if bind.dialect.name == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION specs_guard_approved() RETURNS trigger AS $$
        DECLARE parent_status text;
        BEGIN
          IF TG_TABLE_NAME = 'process_spec_revisions' THEN
            IF OLD.status = 'APPROVED' THEN
              RAISE EXCEPTION 'Approved revisions are immutable';
            END IF;
          ELSIF TG_TABLE_NAME = 'process_parameters' THEN
            SELECT status INTO parent_status FROM process_spec_revisions WHERE id = OLD.revision_id;
            IF parent_status = 'APPROVED' THEN
              RAISE EXCEPTION 'Approved parameters are immutable';
            END IF;
          END IF;
          RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER guard_approved_revision BEFORE UPDATE OR DELETE ON process_spec_revisions
          FOR EACH ROW EXECUTE FUNCTION specs_guard_approved();
        CREATE TRIGGER guard_approved_parameter BEFORE UPDATE OR DELETE ON process_parameters
          FOR EACH ROW EXECUTE FUNCTION specs_guard_approved();
        CREATE OR REPLACE FUNCTION specs_guard_audit() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Audit is append-only'; END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER guard_audit BEFORE UPDATE OR DELETE ON audit_log
          FOR EACH ROW EXECUTE FUNCTION specs_guard_audit();
        CREATE OR REPLACE FUNCTION specs_guard_current() RETURNS trigger AS $$
        BEGIN
          IF NEW.current_approved_revision_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM process_spec_revisions r
            WHERE r.id = NEW.current_approved_revision_id
              AND r.process_spec_id = NEW.id AND r.status = 'APPROVED') THEN
            RAISE EXCEPTION 'Current revision must be approved and belong to this spec';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER guard_current BEFORE INSERT OR UPDATE OF current_approved_revision_id ON process_specs
          FOR EACH ROW EXECUTE FUNCTION specs_guard_current();
        """)


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for trigger, table in (("guard_current", "process_specs"),
                               ("guard_audit", "audit_log"),
                               ("guard_approved_parameter", "process_parameters"),
                               ("guard_approved_revision", "process_spec_revisions")):
            op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        for function in ("specs_guard_current", "specs_guard_audit", "specs_guard_approved"):
            op.execute(f"DROP FUNCTION IF EXISTS {function}()")
    initial_tables = [table for table in Base.metadata.sorted_tables
                      if table.name not in {"pdf_templates", "process_templates"}]
    Base.metadata.drop_all(bind=bind, tables=initial_tables)
