import { ArrowRight, FileText, MessagesSquare, SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Loading,
  PageHeader,
  SearchBox,
  Select,
} from "../components/ui";
import { api } from "../lib/api";
import {
  cx,
  fmtTime,
  freshnessTone,
  reviewTone,
  routeTone,
  toneClasses,
} from "../lib/format";
import type { RecordSummary, RouteDef } from "../lib/types";

const FILTER_KEYS = [
  "source_type",
  "person",
  "route",
  "review_state",
  "text",
  "override",
  "freshness",
  "search",
] as const;

export function Conversations() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [data, setData] = useState<{
    total: number;
    records: RecordSummary[];
    facets: { people: string[]; routes: { key: string; label: string }[]; review_states: { key: string; label: string }[] };
  } | null>(null);
  const [routes, setRoutes] = useState<RouteDef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  const filters = useMemo(() => {
    const out: Record<string, string> = {};
    FILTER_KEYS.forEach((key) => {
      const value = params.get(key);
      if (value) out[key] = value;
    });
    return out;
  }, [params]);

  const load = useCallback(() => {
    setLoading(true);
    api
      .records(filters)
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.meta().then((meta) => setRoutes(meta.routes)).catch(() => undefined);
  }, []);

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (!value) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const activeCount = FILTER_KEYS.filter((key) => params.get(key)).length;
  const routeToneMap = new Map(routes.map((route) => [route.key, route.tone]));
  const routeLabelMap = new Map(routes.map((route) => [route.key, route.label]));

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Conversations"
        title="Selected conversation inbox"
        description={
          <>
            Every imported record appears once, identified by <code className="rounded bg-slate-100 px-1 py-0.5 text-[11.5px]">(source_type, source_id)</code>.
            Missing text is shown as an intake state, never as a concluded conversation.
          </>
        }
        actions={
          <>
            <Button onClick={() => setShowFilters((value) => !value)}>
              <SlidersHorizontal className="h-3.5 w-3.5" />
              {showFilters ? "Hide filters" : "Filters"}
              {activeCount > 0 ? <Badge tone="accent">{activeCount}</Badge> : null}
            </Button>
            <Button onClick={load} disabled={loading}>
              Refresh
            </Button>
          </>
        }
      />

      <Card className="p-3">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
          <div className="min-w-0 flex-1">
            <SearchBox value={params.get("search") ?? ""} onChange={(value) => setFilter("search", value)} />
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="w-36">
              <Select
                ariaLabel="Filter by source type"
                value={params.get("source_type") ?? ""}
                onChange={(value) => setFilter("source_type", value)}
                options={[
                  { value: "", label: "All types" },
                  { value: "call", label: "Calls" },
                  { value: "meeting", label: "Meetings" },
                ]}
              />
            </div>
            <div className="w-44">
              <Select
                ariaLabel="Filter by review state"
                value={params.get("review_state") ?? ""}
                onChange={(value) => setFilter("review_state", value)}
                options={[
                  { value: "", label: "Any review state" },
                  { value: "needs_review", label: "Needs review (+ awaiting text)" },
                  { value: "unreviewed", label: "Not yet reviewed" },
                  { value: "reviewed", label: "Reviewed" },
                  { value: "awaiting_text", label: "Awaiting usable text" },
                ]}
              />
            </div>
            {activeCount > 0 ? (
              <Button variant="ghost" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
                Clear all
              </Button>
            ) : null}
          </div>
        </div>

        {showFilters ? (
          <div className="mt-3 grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-2 xl:grid-cols-5">
            <Field label="Representative / organiser">
              <Select
                ariaLabel="Filter by person"
                value={params.get("person") ?? ""}
                onChange={(value) => setFilter("person", value)}
                options={[
                  { value: "", label: "All people" },
                  ...(data?.facets.people ?? []).map((name) => ({ value: name, label: name })),
                ]}
              />
            </Field>
            <Field label="Route category">
              <Select
                ariaLabel="Filter by route"
                value={params.get("route") ?? ""}
                onChange={(value) => setFilter("route", value)}
                options={[
                  { value: "", label: "All routes" },
                  ...(data?.facets.routes ?? []).map((route) => ({ value: route.key, label: route.label })),
                ]}
              />
            </Field>
            <Field label="Transcript">
              <Select
                ariaLabel="Filter by transcript availability"
                value={params.get("text") ?? ""}
                onChange={(value) => setFilter("text", value)}
                options={[
                  { value: "", label: "Any availability" },
                  { value: "usable", label: "Usable text supplied" },
                  { value: "missing", label: "No usable text" },
                ]}
              />
            </Field>
            <Field label="Manual override">
              <Select
                ariaLabel="Filter by manual override"
                value={params.get("override") ?? ""}
                onChange={(value) => setFilter("override", value)}
                options={[
                  { value: "", label: "Any" },
                  { value: "yes", label: "Overridden" },
                  { value: "no", label: "Automated only" },
                ]}
              />
            </Field>
            <Field label="Analysis freshness">
              <Select
                ariaLabel="Filter by analysis freshness"
                value={params.get("freshness") ?? ""}
                onChange={(value) => setFilter("freshness", value)}
                options={[
                  { value: "", label: "Any freshness" },
                  { value: "current", label: "Current" },
                  { value: "pending_review", label: "Pending review" },
                  { value: "stale", label: "Stale" },
                  { value: "unavailable", label: "Unavailable (no text)" },
                  { value: "none", label: "No analysis" },
                ]}
              />
            </Field>
          </div>
        ) : null}
      </Card>

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-2.5">
          <p className="text-[12px] text-slate-500">
            {loading ? "Loading…" : <><strong className="font-semibold text-slate-800">{data?.total ?? 0}</strong> records in this view</>}
            {activeCount > 0 ? " · filtered" : " · all selected records"}
          </p>
          <p className="text-[11px] text-slate-400">Select a row to inspect evidence, routes and corrections.</p>
        </div>

        {loading && !data ? (
          <Loading />
        ) : data && data.records.length === 0 ? (
          <EmptyState
            icon={<MessagesSquare className="h-8 w-8" />}
            title={activeCount ? "No records match these filters" : "No records imported"}
            body={
              activeCount
                ? "Relax a filter or clear them all. Filters are recorded in the URL, so you can share the exact view."
                : "Use the Import lab to load the supplied deliveries."
            }
            action={
              activeCount ? (
                <Button onClick={() => setParams(new URLSearchParams(), { replace: true })}>Clear filters</Button>
              ) : (
                <Button onClick={() => navigate("/imports")}>Open Import lab</Button>
              )
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="table-compact w-full min-w-[1080px]">
              <thead className="bg-slate-50/80">
                <tr className="border-b border-slate-200 text-left">
                  <th className="px-3 py-2">Record</th>
                  <th className="px-3 py-2">When</th>
                  <th className="px-3 py-2">Person</th>
                  <th className="px-3 py-2">Text</th>
                  <th className="px-3 py-2">Suggested → Effective</th>
                  <th className="px-3 py-2">Review</th>
                  <th className="px-3 py-2">Rev</th>
                  <th className="px-3 py-2">Analysis</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data?.records.map((record) => (
                  <tr
                    key={`${record.source_type}-${record.source_id}`}
                    className="group cursor-pointer hover:bg-indigo-50/30"
                    onClick={() => navigate(`/conversations/${record.source_type}/${record.source_id}${window.location.search}`)}
                  >
                    <td className="px-3 py-2.5">
                      <div className="flex items-start gap-2">
                        <span
                          className={cx(
                            "mt-0.5 inline-flex h-5 min-w-[34px] items-center justify-center rounded px-1 text-[10.5px] font-semibold uppercase",
                            record.source_type === "call"
                              ? "bg-indigo-50 text-indigo-700"
                              : "bg-teal-50 text-teal-700",
                          )}
                        >
                          {record.record_ref}
                        </span>
                        <div className="min-w-0">
                          <div className="max-w-[240px] truncate font-medium text-slate-800" title={record.title ?? record.owner_name ?? ""}>
                            {record.title ?? (record.source_type === "call" ? `Call ${record.record_ref}` : `Meeting ${record.record_ref}`)}
                          </div>
                          <div className="mt-0.5 text-[11px] text-slate-400">
                            {record.source_type} · {record.source_id.slice(0, 10)}…
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-slate-600">
                      <div>{fmtTime(record.started_at_local)}</div>
                      <div className="text-[11px] text-slate-400">{record.activity_date ?? "no timestamp"}</div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="max-w-[150px] truncate text-slate-700" title={record.owner_name ?? "Not supplied"}>
                        {record.owner_name ?? <span className="text-slate-400">Not supplied</span>}
                      </div>
                      <div className="text-[11px] text-slate-400">{record.owner_role_label}</div>
                    </td>
                    <td className="px-3 py-2.5">
                      {record.has_usable_text ? (
                        <Badge tone="success">
                          <FileText className="h-3 w-3" /> Usable
                        </Badge>
                      ) : (
                        <Badge tone="muted" title={record.unavailable_reason ?? undefined}>
                          No text
                        </Badge>
                      )}
                      {record.source_outcome ? (
                        <div className="mt-1 text-[11px] text-slate-400">outcome: {record.source_outcome}</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex max-w-[250px] flex-wrap gap-1">
                        {record.effective_routes.map((route) => (
                          <Badge key={route} tone={routeTone(routeToneMap.get(route) ?? "neutral")} title={routeLabelMap.get(route)}>
                            {routeLabelMap.get(route) ?? route.replace(/_/g, " ")}
                          </Badge>
                        ))}
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-1 text-[10.5px] text-slate-400">
                        <span>suggested:</span>
                        {record.suggested_routes.map((route) => (
                          <span key={route} className={cx(route !== record.effective_routes[0] && "text-slate-500")}>
                            {routeLabelMap.get(route) ?? route}
                          </span>
                        ))}
                        {record.manual_override ? (
                          <Badge tone="accent" className="ml-1">
                            Manual
                          </Badge>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge tone={reviewTone(record.review_state)}>{record.review_label}</Badge>
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={cx(
                          "inline-flex h-5 min-w-5 items-center justify-center rounded text-[11px] font-semibold",
                          record.applied_revision > 1 ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600",
                        )}
                        title={`Applied source revision ${record.applied_revision}`}
                      >
                        {record.applied_revision}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      {record.analysis ? (
                        <div className="flex flex-col gap-1">
                          <Badge tone={freshnessTone(record.analysis_freshness)}>{record.analysis_freshness_label}</Badge>
                          <span className="text-[10.5px] text-slate-400">{record.analysis.origin_label}</span>
                        </div>
                      ) : (
                        <Badge tone="muted">No analysis</Badge>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <ArrowRight className="ml-auto h-3.5 w-3.5 text-slate-300 transition-colors group-hover:text-indigo-600" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className={cx("flex flex-wrap gap-3 text-[11.5px] text-slate-500")}>
        <span className="inline-flex items-center gap-1">
          <span className={cx("h-2 w-2 rounded-full", toneClasses.success.split(" ")[0])} /> Usable text supplied
        </span>
        <span className="inline-flex items-center gap-1">
          <span className={cx("h-2 w-2 rounded-full", toneClasses.warning.split(" ")[0])} /> Needs manager review
        </span>
        <span className="inline-flex items-center gap-1">
          <span className={cx("h-2 w-2 rounded-full", toneClasses.accent.split(" ")[0])} /> Manual route override
        </span>
        <span className="ml-auto inline-flex items-center gap-1">
          Rev 2 <span className="text-slate-400">means the record was updated by a later delivery</span>
        </span>
      </div>
    </div>
  );
}
