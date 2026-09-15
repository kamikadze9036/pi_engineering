from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON, BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


ID = BigInteger().with_variant(Integer, "sqlite")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    __table_args__ = (CheckConstraint("role IN ('ENGINEER','APPROVER','ADMIN')", name="user_role"),)


class Assignment(Base):
    __tablename__ = "machine_tool_assignments"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    mes_machine_ref: Mapped[str] = mapped_column(String(120))
    mes_tool_ref: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    __table_args__ = (
        UniqueConstraint("mes_machine_ref", "mes_tool_ref", name="uq_mes_assignment"),
        CheckConstraint("mes_machine_ref <> '' AND mes_tool_ref <> ''", name="assignment_refs_nonempty"),
    )


class Spec(Base):
    __tablename__ = "process_specs"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("machine_tool_assignments.id", ondelete="RESTRICT"), unique=True)
    lifecycle: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    current_approved_revision_id: Mapped[int | None] = mapped_column(ForeignKey("process_spec_revisions.id", ondelete="RESTRICT"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    assignment: Mapped[Assignment] = relationship()
    __table_args__ = (CheckConstraint("lifecycle IN ('ACTIVE','OBSOLETE')", name="spec_lifecycle"),)


class Revision(Base):
    __tablename__ = "process_spec_revisions"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    process_spec_id: Mapped[int] = mapped_column(ForeignKey("process_specs.id", ondelete="RESTRICT"))
    revision_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    change_reason: Mapped[str] = mapped_column(Text, default="")
    product_name: Mapped[str] = mapped_column(String(255), default="")
    material_name: Mapped[str] = mapped_column(String(255), default="")
    process_note: Mapped[str] = mapped_column(Text, default="")
    mes_machine_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mes_machine_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mes_tool_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mes_tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    parameters: Mapped[list["ParameterValue"]] = relationship(order_by="ParameterValue.sort_order")
    __table_args__ = (
        UniqueConstraint("process_spec_id", "revision_number", name="uq_spec_revision_number"),
        CheckConstraint("revision_number > 0", name="revision_positive"),
        CheckConstraint("status IN ('DRAFT','IN_REVIEW','APPROVED','CANCELLED')", name="revision_status"),
        Index("uq_open_revision", "process_spec_id", unique=True,
              postgresql_where=text("status IN ('DRAFT','IN_REVIEW')"),
              sqlite_where=text("status IN ('DRAFT','IN_REVIEW')")),
    )


class ParameterDefinition(Base):
    __tablename__ = "parameter_definitions"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    code: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(120))
    value_type: Mapped[str] = mapped_column(String(20), default="NUMERIC")
    unit: Mapped[str] = mapped_column(String(40), default="")
    position_kind: Mapped[str] = mapped_column(String(20), default="NONE")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        CheckConstraint("value_type IN ('NUMERIC','TEXT','BOOLEAN')", name="definition_type"),
        CheckConstraint("position_kind IN ('NONE','SEQUENCE','LABEL')", name="definition_position"),
    )


class ParameterValue(Base):
    __tablename__ = "process_parameters"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("process_spec_revisions.id", ondelete="RESTRICT"))
    definition_id: Mapped[int] = mapped_column(ForeignKey("parameter_definitions.id", ondelete="RESTRICT"))
    position_key: Mapped[str] = mapped_column(String(120), default="")
    position_label: Mapped[str] = mapped_column(String(120), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    numeric_target: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    numeric_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    numeric_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    unit: Mapped[str] = mapped_column(String(40), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    definition_code: Mapped[str] = mapped_column(String(120))
    definition_name: Mapped[str] = mapped_column(String(255))
    definition_category: Mapped[str] = mapped_column(String(120))
    definition_type: Mapped[str] = mapped_column(String(20))
    __table_args__ = (
        UniqueConstraint("revision_id", "definition_id", "position_key", name="uq_revision_parameter_position"),
        CheckConstraint("numeric_min IS NULL OR numeric_max IS NULL OR numeric_min <= numeric_max", name="parameter_min_max"),
        CheckConstraint("numeric_min IS NULL OR numeric_target IS NULL OR numeric_min <= numeric_target", name="parameter_min_target"),
        CheckConstraint("numeric_max IS NULL OR numeric_target IS NULL OR numeric_target <= numeric_max", name="parameter_target_max"),
    )


class AuditEntry(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    entity_type: Mapped[str] = mapped_column(String(120))
    entity_id: Mapped[int] = mapped_column(ID)
    action: Mapped[str] = mapped_column(String(120))
    before_data: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id", "created_at"),)


class PdfDocument(Base):
    __tablename__ = "pdf_documents"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("process_spec_revisions.id", ondelete="RESTRICT"))
    template_version: Mapped[str] = mapped_column(String(40))
    storage_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    generated_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    __table_args__ = (UniqueConstraint("revision_id", "template_version", name="uq_pdf_revision_template"),)


class PdfTemplate(Base):
    """A published version is immutable; editing creates another version."""
    __tablename__ = "pdf_templates"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    version: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    settings: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
