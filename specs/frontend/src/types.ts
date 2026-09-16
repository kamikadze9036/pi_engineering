export type User = { id: number; username: string; role: 'ENGINEER' | 'APPROVER' | 'ADMIN'; name: string; csrf: string };
export type MesItem = { ref: string; code: string; name: string };
export type Definition = {
  id: number; code: string; name: string; category: string;
  value_type: 'NUMERIC' | 'TEXT' | 'BOOLEAN'; unit: string;
  position_kind: 'NONE' | 'SEQUENCE' | 'LABEL';
  positions: { key: string; label: string }[];
};
export type Parameter = {
  definition_id: number; definition_code: string; definition_name: string;
  definition_category: string; definition_type: string;
  position_key: string; position_label: string;
  numeric_target: string | null; numeric_min: string | null; numeric_max: string | null;
  text_value: string | null; boolean_value: boolean | null; unit: string; note: string;
};
export type Revision = {
  id: number; process_spec_id: number; revision_number: number; status: 'DRAFT' | 'IN_REVIEW' | 'APPROVED' | 'CANCELLED';
  row_version: number; product_name: string; material_name: string; process_note: string;
  change_reason: string; created_by: number; created_at: string;
  approved_by: number | null; approved_at: string | null;
  mes_machine_code: string | null; mes_machine_name: string | null;
  mes_tool_code: string | null; mes_tool_name: string | null;
  parameters: Parameter[];
};
export type Spec = {
  id: number; machine_ref: string; tool_ref: string; lifecycle: string;
  current_approved_revision_id: number | null; revisions: Revision[];
};
export type Template = { version: string; title: string; settings: {
  accent_color: string; section_color: string; show_english_subtitle: boolean;
} };
export type ProcessTemplate = {
  id: number; name: string; description: string; source_revision_id: number | null;
  is_system: boolean; parameter_count: number;
};
export type BugReport = {
  id: number; reporter_id: number; message: string; page: string;
  status: 'OPEN' | 'DONE'; created_at: string; resolved_at: string | null;
};
