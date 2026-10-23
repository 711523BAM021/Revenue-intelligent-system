import type {
  BriefData,
  ExportManifest,
  ImportBatch,
  Meta,
  Metrics,
  RecordDetail,
  RecordSummary,
  ReplayResult,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    const message =
      typeof detail === "object" && detail && "detail" in detail
        ? typeof (detail as { detail: unknown }).detail === "string"
          ? ((detail as { detail: string }).detail)
          : JSON.stringify((detail as { detail: unknown }).detail)
        : `Request failed (${response.status})`;
    throw new ApiError(message, response.status, detail);
  }
  return (await response.json()) as T;
}

function qs(params: Record<string, string | null | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "" && value !== "all") {
      search.set(key, value);
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export type RecordFilters = Record<string, string | null | undefined>;

export const api = {
  meta: () => request<Meta>("/api/meta"),
  metrics: (filters: RecordFilters = {}) => request<Metrics>(`/api/metrics${qs(filters)}`),
  records: (filters: RecordFilters = {}) =>
    request<{
      total: number;
      records: RecordSummary[];
      facets: {
        people: string[];
        routes: { key: string; label: string }[];
        review_states: { key: string; label: string }[];
        dates: string[];
      };
      filters: RecordFilters;
    }>(`/api/records${qs(filters)}`),
  record: (type: string, id: string) =>
    request<RecordDetail>(`/api/records/${type}/${encodeURIComponent(id)}`),
  setOverride: (type: string, id: string, routes: string[], reason: string) =>
    request<RecordSummary>(`/api/records/${type}/${encodeURIComponent(id)}/override`, {
      method: "PATCH",
      body: JSON.stringify({ routes, reason }),
    }),
  resetOverride: (type: string, id: string) =>
    request<RecordSummary>(`/api/records/${type}/${encodeURIComponent(id)}/override`, {
      method: "DELETE",
    }),
  setReview: (type: string, id: string, state: string, note: string) =>
    request<RecordSummary>(`/api/records/${type}/${encodeURIComponent(id)}/review`, {
      method: "PATCH",
      body: JSON.stringify({ state, note }),
    }),
  saveAnalysis: (
    type: string,
    id: string,
    payload: {
      summary: string;
      why_it_matters: string;
      evidence: unknown[];
      risks: string[];
      opportunities: string[];
      uncertainties: string[];
      next_action: string;
      action_owner: string | null;
      owner_basis: string | null;
    },
  ) =>
    request<RecordDetail>(`/api/records/${type}/${encodeURIComponent(id)}/analysis`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  markPending: (type: string, id: string) =>
    request<RecordSummary>(`/api/records/${type}/${encodeURIComponent(id)}/analysis/pending`, {
      method: "POST",
    }),
  brief: () => request<BriefData>("/api/brief"),
  imports: () =>
    request<{
      datasets: { dataset: string; filename: string; exists: boolean; bytes: number }[];
      batches: ImportBatch[];
      current: { records: number; revisions: Record<string, number> };
    }>("/api/imports"),
  importDataset: (dataset: string, shuffle = false) =>
    request<{
      batch: {
        batch_id: string;
        filename: string;
        delivery_revision: number;
        inserted: number;
        updated: number;
        ignored: number;
        status: string;
        warnings: string[];
        shuffled: boolean;
      };
      metrics: Metrics["totals"];
    }>("/api/imports", {
      method: "POST",
      body: JSON.stringify({ dataset, shuffle }),
    }),
  demoLoad: () =>
    request<{ message: string; batches: Record<string, unknown>[]; metrics: Metrics["totals"] }>(
      "/api/demo/load",
      { method: "POST" },
    ),
  reset: () => request<{ status: string; message: string }>("/api/admin/reset", { method: "POST" }),
  replay: () => request<ReplayResult>("/api/replay", { method: "POST" }),
  quality: () =>
    request<{
      counts: Record<string, number>;
      lists: Record<string, string[]>;
      unverified_evidence: { record_ref: string; evidence: { quote: string; turn?: number } }[];
      notes: string[];
      metrics_notes: { metric: string; definition: string }[];
    }>("/api/quality"),
  exports: () =>
    request<{
      history: {
        version: number;
        created_at: string;
        record_count: number;
        superseded: boolean;
        archive_path: string;
        state_hash: string;
      }[];
      current: ExportManifest | null;
      version: number | null;
      created_at: string | null;
      download: { archive: string; manifest_json: string; manifest_csv: string } | null;
    }>("/api/exports"),
  createExport: () =>
    request<{ created: boolean; version: number; message: string; manifest: ExportManifest }>(
      "/api/exports",
      { method: "POST" },
    ),
  exportDownloadUrl: (kind: "archive" | "manifest_json" | "manifest_csv") =>
    `${BASE}/api/exports/current/${kind === "archive" ? "archive.zip" : kind === "manifest_json" ? "manifest.json" : "manifest.csv"}`,
};
