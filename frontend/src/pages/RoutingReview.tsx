import { ExternalLink, GitBranch, Info, ListChecks, Route as RouteIcon, ShieldQuestion } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, EmptyState, ErrorState, Loading, PageHeader, SectionHeader } from "../components/ui";
import { api } from "../lib/api";
import { cx, fmtTime, freshnessTone, reviewTone, routeTone } from "../lib/format";
import type { RecordSummary, RouteDef } from "../lib/types";

type Tab = "decision" | "overrides" | "text" | "all";

const TABS: { key: Tab; label: string }[] = [
  { key: "decision", label: "Needs a decision" },
  { key: "overrides", label: "Manual overrides" },
  { key: "text", label: "With usable text" },
  { key: "all", label: "All records" },
];

export function RoutingReview() {
  const [records, setRecords] = useState<RecordSummary[]>([]);
  const [routes, setRoutes] = useState<RouteDef[]>([]);
  const [tab, setTab] = useState<Tab>("decision");
  const [routeFilter, setRouteFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([api.records(), api.meta()])
      .then(([data, meta]) => {
        setRecords(data.records);
        setRoutes(meta.routes);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const routeMap = useMemo(() => new Map(routes.map((route) => [route.key, route])), [routes]);

  const filtered = useMemo(() => {
    let list = records;
    if (tab === "decision") {
      list = records.filter(
        (record) => record.review_state === "needs_review" || record.review_state === "awaiting_text",
      );
    } else if (tab === "overrides") {
      list = records.filter((record) => record.manual_override);
    } else if (tab === "text") {
      list = records.filter((record) => record.has_usable_text);
    }
    if (routeFilter) {
      list = list.filter(
        (record) =>
          record.effective_routes.includes(routeFilter as never) ||
          record.suggested_routes.includes(routeFilter as never),
      );
    }
    return list;
  }, [records, tab, routeFilter]);

  const decisionCount = records.filter(
    (record) => record.review_state === "needs_review" || record.review_state === "awaiting_text",
  ).length;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Routing & Review"
        title="Decide where each conversation belongs"
        description="A conversation can need several destinations, or a human decision. Automated suggestions and manager decisions are always shown separately."
        actions={
          <>
            <Button onClick={load} disabled={loading}>Refresh</Button>
          </>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_330px]">
        <div className="space-y-4">
          <Card className="p-3">
            <div className="flex flex-wrap items-center gap-1.5">
              {TABS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setTab(item.key)}
                  className={cx(
                    "rounded-md px-2.5 py-1.5 text-[12.5px] font-medium",
                    tab === item.key ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100",
                  )}
                >
                  {item.label}
                  {item.key === "decision" ? (
                    <span className={cx("ml-1.5 text-[11px]", tab === item.key ? "text-white/70" : "text-slate-400")}>
                      {decisionCount}
                    </span>
                  ) : null}
                </button>
              ))}
              <div className="ml-auto flex items-center gap-2">
                <label className="text-[11px] text-slate-500" htmlFor="route-filter">Route</label>
                <select
                  id="route-filter"
                  value={routeFilter}
                  onChange={(event) => setRouteFilter(event.target.value)}
                  className="rounded-md border border-slate-300 px-2 py-1 text-[12px]"
                >
                  <option value="">Any route</option>
                  {routes.map((route) => (
                    <option key={route.key} value={route.key}>{route.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </Card>

          {error ? <ErrorState message={error} onRetry={load} /> : null}

          {loading && records.length === 0 ? (
            <Loading label="Loading routing queue" />
          ) : filtered.length === 0 ? (
            <Card>
              <EmptyState
                icon={<ListChecks className="h-8 w-8" />}
                title={tab === "decision" ? "No records need a decision" : "Nothing in this view"}
                body={
                  tab === "decision"
                    ? "Every text-bearing record has been reviewed and no record is awaiting text. Switch tabs to browse the rest of the inbox."
                    : "Try another tab or clear the route filter."
                }
              />
            </Card>
          ) : (
            <div className="space-y-2.5">
              {filtered.map((record) => {
                const differs =
                  record.manual_override ||
                  record.suggested_routes.length !== record.effective_routes.length ||
                  record.suggested_routes.some((route) => !record.effective_routes.includes(route));
                return (
                  <Card key={`${record.source_type}-${record.source_id}`} className="p-3.5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span
                            className={cx(
                              "inline-flex h-5 items-center rounded px-1.5 text-[10.5px] font-semibold uppercase",
                              record.source_type === "call" ? "bg-indigo-50 text-indigo-700" : "bg-teal-50 text-teal-700",
                            )}
                          >
                            {record.record_ref}
                          </span>
                          <Badge tone={reviewTone(record.review_state)}>{record.review_label}</Badge>
                          <Badge tone={freshnessTone(record.analysis_freshness)}>{record.analysis_freshness_label}</Badge>
                          {record.manual_override ? <Badge tone="accent">Manual</Badge> : null}
                          <span className="text-[11px] text-slate-400">{fmtTime(record.started_at_local)} IST</span>
                        </div>
                        <h3 className="mt-1 truncate text-[13.5px] font-medium text-slate-800">
                          {record.title ?? `${record.source_type === "call" ? "Call" : "Meeting"} ${record.record_ref}`}
                        </h3>
                        <p className="mt-0.5 text-[11.5px] text-slate-500">
                          {record.has_usable_text
                            ? record.analysis?.content.summary
                              ? `${record.analysis.content.summary.slice(0, 180)}${record.analysis.content.summary.length > 180 ? "…" : ""}`
                              : "Usable text, no analysis."
                            : record.unavailable_reason ?? "No usable supplied text; intake state only."}
                        </p>
                      </div>
                      <Link
                        to={`/conversations/${record.source_type}/${record.source_id}`}
                        className="inline-flex shrink-0 items-center gap-1 rounded-md border border-slate-300 px-2.5 py-1 text-[12px] font-medium text-slate-700 hover:bg-slate-50"
                      >
                        Inspect <ExternalLink className="h-3 w-3" />
                      </Link>
                    </div>

                    <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-100 pt-2.5">
                      <div>
                        <div className="label-xs mb-1">Suggested</div>
                        <div className="flex flex-wrap gap-1">
                          {record.suggested_routes.map((route) => (
                            <Badge key={route} tone={routeTone(routeMap.get(route)?.tone ?? "neutral")}>
                              {routeMap.get(route)?.label ?? route}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <GitBranch className="hidden h-4 w-4 text-slate-300 sm:block" />
                      <div>
                        <div className="label-xs mb-1">Effective</div>
                        <div className="flex flex-wrap gap-1">
                          {record.effective_routes.map((route) => (
                            <Badge key={route} tone={routeTone(routeMap.get(route)?.tone ?? "neutral")}>
                              {routeMap.get(route)?.label ?? route}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      {differs ? (
                        <span className="text-[11.5px] text-indigo-700">
                          Manager decision differs from the automated suggestion
                        </span>
                      ) : null}
                      <span className="ml-auto text-[11px] text-slate-400">
                        {record.analysis?.origin_label ?? "No analysis"} · rev {record.applied_revision}
                      </span>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <Card className="p-4">
            <SectionHeader
              icon={<RouteIcon className="h-4 w-4" />}
              title="Routing taxonomy"
              description="Seven destinations. A record can hold more than one when the conversation genuinely serves more than one purpose."
            />
            <ul className="mt-3 space-y-2.5">
              {routes.map((route) => (
                <li key={route.key} className="rounded-md border border-slate-200 p-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <Badge tone={routeTone(route.tone)}>{route.label}</Badge>
                    <span className="text-[11px] text-slate-400">
                      {records.filter((record) => record.effective_routes.includes(route.key as never)).length}
                    </span>
                  </div>
                  <p className="mt-1.5 text-[11.5px] leading-5 text-slate-600">{route.description}</p>
                </li>
              ))}
            </ul>
          </Card>

          <Card className="p-4">
            <SectionHeader icon={<ShieldQuestion className="h-4 w-4" />} title="How a decision is made" />
            <ol className="mt-2 space-y-2 text-[12px] leading-5 text-slate-600">
              <li><span className="font-medium text-slate-800">1.</span> Read the supplied text, not the title or organiser.</li>
              <li><span className="font-medium text-slate-800">2.</span> Identify who the other party is: prospect, existing customer, partner, supplier or internal.</li>
              <li><span className="font-medium text-slate-800">3.</span> Separate product interest from a confirmed purchase, and a suggestion from a commitment.</li>
              <li><span className="font-medium text-slate-800">4.</span> If the evidence does not settle it, route to Human review and say why.</li>
              <li><span className="font-medium text-slate-800">5.</span> Record a correction reason so the next person can audit the decision.</li>
            </ol>
            <p className="mt-3 flex items-start gap-1.5 rounded-md bg-slate-50 px-2.5 py-2 text-[11.5px] leading-5 text-slate-600">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
              A manual override is kept even when a newer source revision arrives. Only an explicit reset returns the
              record to the automated suggestion.
            </p>
          </Card>
        </aside>
      </div>
    </div>
  );
}
