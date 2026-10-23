export type RouteKey =
  | "deal_next_steps"
  | "customer_followup"
  | "sales_coaching"
  | "customer_success"
  | "internal_vendor"
  | "no_action"
  | "needs_review";

export interface RouteDef {
  key: RouteKey;
  label: string;
  slug: string;
  description: string;
  tone: string;
  order: number;
}

export interface Meta {
  reporting_date: string;
  timezone: string;
  routes: RouteDef[];
  review_states: { key: string; label: string }[];
  datasets: { dataset: string; filename: string; exists: boolean; bytes: number }[];
  counts: { records: number; imports: number; exports: number };
}

export interface Analysis {
  content: {
    summary: string;
    why_it_matters: string;
    evidence: Evidence[];
    risks: string[];
    opportunities: string[];
    uncertainties: string[];
    next_action: string;
    action_owner: string | null;
    owner_basis: string | null;
    suggested_routes: RouteKey[];
    route_rationale: string;
    route_trace?: { rule: string; outcome: string; detail: string }[];
    review_status?: string;
    analysis_basis?: string;
  };
  origin: string;
  origin_label: string;
  author: string | null;
  freshness: string;
  freshness_label: string;
  source_revision: number;
  engine_version: string;
  generated_at: string;
  updated_at: string;
}

export interface Evidence {
  kind: "turn" | "quote";
  turn?: number;
  quote: string;
  note?: string;
  verified?: boolean;
}

export interface RecordSummary {
  id: number;
  source_type: "call" | "meeting";
  source_id: string;
  record_ref: string;
  title: string | null;
  started_at_utc: string | null;
  started_at_local: string | null;
  activity_date: string | null;
  owner_name: string | null;
  owner_kind: "call_representative" | "meeting_organiser";
  owner_role_label: string;
  owner_email: string | null;
  direction: string | null;
  duration_seconds: number | null;
  source_outcome: string | null;
  is_connected: boolean | null;
  is_conversation: boolean | null;
  recording_status: string | null;
  has_transcript_flag: boolean | null;
  has_usable_text: boolean;
  unavailable_reason: string | null;
  applied_revision: number;
  first_revision: number;
  last_batch_id: string | null;
  last_revision_changed_at: string | null;
  processing_state: string;
  processing_label: string;
  suggested_routes: RouteKey[];
  suggested_route_labels: string[];
  effective_routes: RouteKey[];
  effective_route_labels: string[];
  manual_override: boolean;
  override: { routes: RouteKey[]; reason: string | null; updated_at: string } | null;
  review_state: string;
  review_label: string;
  review_note: string | null;
  review_updated_at: string | null;
  analysis_freshness: string;
  analysis_freshness_label: string;
  routing_method: string | null;
  routing_method_label: string;
  routing_rationale: string | null;
  routing_trace: { rule: string; outcome: string; detail: string }[];
  routing_computed_at: string | null;
  analysis: Analysis | null;
}

export interface Turn {
  turn: number;
  speaker: string | null;
  text: string;
  starts_at_seconds: number | null;
  timecode: string | null;
}

export interface RecordDetail extends RecordSummary {
  transcript_text: string | null;
  turns: Turn[] | null;
  history: { kind: string; detail: Record<string, unknown>; created_at: string }[];
  archived_analyses: {
    origin: string;
    freshness: string;
    source_revision: number;
    archived_at: string;
    reason: string | null;
  }[];
  import_events: {
    batch_id: string;
    filename: string;
    revision: number;
    status: string;
    imported_at: string;
    inserted: number;
    updated: number;
    ignored: number;
    record_actions: Record<string, unknown>[];
  }[];
}

export interface Totals {
  records: number;
  calls: number;
  meetings: number;
  usable_text: number;
  usable_calls: number;
  usable_meetings: number;
  coverage_pct: number | null;
  coverage_denominator: number;
  missing_text: number;
  needs_review: number;
  awaiting_text: number;
  manual_overrides: number;
  multi_route_records: number;
  route_assignments: number;
}

export interface Metrics {
  reporting: { date: string; timezone: string; label: string };
  totals: Totals;
  review_states: { state: string; label: string; count: number }[];
  routes: {
    effective: { route: RouteKey; label: string; count: number; suggested_count: number }[];
    assignments: number;
    records: number;
    multi_route_records: number;
  };
  activity_by_day: { date: string; calls: number; meetings: number; records: number }[];
  call_reps: { name: string; calls: number; usable_text: number }[];
  meeting_organisers: { name: string; meetings: number; usable_text: number }[];
  unassigned: { calls: number; meetings: number };
  connection: {
    connected: number;
    disconnected: number;
    unknown: number;
    denominator: number;
    rate_pct: number | null;
    calls_total: number;
  };
  source_outcomes: { outcome: string; count: number }[];
  freshness: { state: string; count: number }[];
  analysis_origin: { origin: string; count: number }[];
  filters: Record<string, string | null>;
}

export interface BriefItem {
  record_ref: string;
  source_id: string;
  text: string;
  evidence: Evidence[];
  record: RecordSummary | null;
}

export interface BriefData {
  brief: {
    date: string;
    title: string;
    standfirst: string;
    scope_note: string;
    sections: { id: string; title: string; intro?: string; items: BriefItem[] }[];
    uncertainty: { title: string; items: string[] };
  };
  findings: {
    id: string;
    title: string;
    observation: string;
    why_it_matters: string;
    evidence: Evidence & { record_ref: string };
    affected_surface: string;
    validated_against: string;
    verified: boolean;
  }[];
  rejected_decision: {
    title: string;
    alternative: string;
    why_rejected: string;
    trade_off: string;
    where_it_appears: string;
    screen: string;
  };
  metrics_notes: { metric: string; definition: string }[];
  metrics: Metrics;
  generated_from: string;
}

export interface ImportBatch {
  id: number;
  batch_id: string;
  filename: string;
  delivery_revision: number;
  status: string;
  imported_at: string;
  inserted: number;
  updated: number;
  ignored: number;
  errors: string[];
  details: {
    warnings?: string[];
    records?: {
      record_ref: string;
      action: string;
      text_changed?: boolean;
      from_revision?: number;
      to_revision?: number;
      stored_revision?: number;
      incoming_revision?: number;
    }[];
  };
}

export interface ExportManifest {
  export_version: number;
  status: string;
  generated_at: string;
  reporting_date: string;
  root: string;
  summary: Totals;
  records: {
    source_type: string;
    source_id: string;
    record_ref: string;
    applied_revision: number;
    suggested_routes: RouteKey[];
    effective_routes: RouteKey[];
    output_paths: string[];
    processing_state: string;
    review_state: string;
    manual_override: boolean;
    analysis_freshness: string;
    title: string | null;
  }[];
  files: string[];
}

export interface ReplayCheck {
  id: string;
  label: string;
  pass: boolean;
  expected: unknown;
  actual: unknown;
  note?: string;
}

export interface ReplayResult {
  available: boolean;
  errors?: string[];
  ran_at?: string;
  isolated?: boolean;
  note?: string;
  steps: {
    title: string;
    description: string;
    observed: Record<string, unknown>;
    at: string;
  }[];
  checks: ReplayCheck[];
  summary: { passed: number; failed: number; total: number };
  m07?: Record<string, unknown>;
}
