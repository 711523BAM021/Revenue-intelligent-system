import {
  ArrowUpRight,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  Info,
  Layers,
  PhoneCall,
  Users,
  Video,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Loading, Metric, PageHeader, SectionHeader, Select } from "../components/ui";
import { api, type RecordFilters } from "../lib/api";
import { cx, pct } from "../lib/format";
import type { Metrics } from "../lib/types";

const ROUTE_COLORS = ["#2549d8", "#4f6ee8", "#7d95f0", "#0f766e", "#b45309", "#64748b", "#be123c"];

export function Overview() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const person = params.get("person") ?? "";
  const sourceType = params.get("source_type") ?? "";

  const filters = useMemo<RecordFilters>(() => ({ person, source_type: sourceType }), [person, sourceType]);

  const load = useCallback(() => {
    setLoading(true);
    api
      .metrics(filters)
      .then((data) => {
        setMetrics(data);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (!value) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const openConversations = (extra: RecordFilters = {}) => {
    const search = new URLSearchParams();
    Object.entries({ ...filters, ...extra }).forEach(([key, value]) => {
      if (value) search.set(key, String(value));
    });
    navigate(`/conversations?${search.toString()}`);
  };

  const loadDemo = async () => {
    setBusy(true);
    try {
      await api.demoLoad();
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (loading && !metrics) return <Loading label="Loading workspace metrics" />;
  if (error && !metrics) return <ErrorState message={error} onRetry={load} />;
  if (!metrics) return null;

  const t = metrics.totals;
  const people = [...metrics.call_reps, ...metrics.meeting_organisers.map((m) => ({ name: m.name, calls: 0 }))];
  const personOptions = [
    { value: "", label: "All people" },
    ...[...new Map(people.map((p) => [p.name, p])).values()].map((p) => ({ value: p.name, label: p.name })),
  ];

  const routeData = metrics.routes.effective.map((route) => ({
    name: route.label,
    count: route.count,
    suggested: route.suggested_count,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Overview"
        title="What needs a manager's attention"
        description={
          <>
            Selected activity for <strong className="font-medium text-slate-700">21 August 2026</strong> in
            Asia/Kolkata. All percentages are computed from the imported records and show their denominators.
          </>
        }
        actions={
          <>
            <Button onClick={() => load()} disabled={loading}>
              Refresh
            </Button>
            <Button variant="primary" onClick={() => openConversations({ text: "usable" })}>
              Review inbox <ArrowUpRight className="h-3.5 w-3.5" />
            </Button>
          </>
        }
      />

      <Card className="flex flex-wrap items-end gap-3 px-4 py-3">
        <div className="w-48">
          <Field label="Person" htmlFor="filter-person">
            <Select
              id="filter-person"
              ariaLabel="Filter by person"
              value={person}
              onChange={(value) => setFilter("person", value)}
              options={personOptions}
            />
          </Field>
        </div>
        <div className="w-40">
          <Field label="Source type" htmlFor="filter-source">
            <Select
              id="filter-source"
              ariaLabel="Filter by source type"
              value={sourceType}
              onChange={(value) => setFilter("source_type", value)}
              options={[
                { value: "", label: "Calls + meetings" },
                { value: "call", label: "Calls only" },
                { value: "meeting", label: "Meetings only" },
              ]}
            />
          </Field>
        </div>
        <p className="ml-auto flex items-center gap-1.5 text-[11.5px] text-slate-500">
          <Info className="h-3.5 w-3.5" />
          A person is a call representative or a meeting organiser. The two are never combined.
        </p>
      </Card>

      {t.records === 0 ? (
        <Card>
          <EmptyState
            icon={<Layers className="h-8 w-8" />}
            title={person || sourceType ? "No records match these filters" : "No deliveries imported yet"}
            body={
              person || sourceType
                ? "Clear the person and source-type filters to see all selected records."
                : "Import the supplied 01_initial.json and 02_update.json through the Import lab, or load the post-update demo state."
            }
            action={
              person || sourceType ? (
                <Button onClick={() => setParams(new URLSearchParams())}>Clear filters</Button>
              ) : (
                <div className="flex gap-2">
                  <Button onClick={() => navigate("/imports")}>Open Import lab</Button>
                  <Button variant="primary" onClick={loadDemo} disabled={busy}>
                    {busy ? "Loading…" : "Load demo state"}
                  </Button>
                </div>
              )
            }
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric
              label="Selected records"
              value={t.records}
              sub={`${t.calls} calls · ${t.meetings} meetings`}
              tone="accent"
              hint="Distinct (source_type, source_id) pairs after applying the highest revision received. Repeat imports never add to this count."
              onClick={() => openConversations()}
            />
            <Metric
              label="Transcript coverage"
              value={pct(t.coverage_pct)}
              sub={`${t.usable_text} of ${t.coverage_denominator} records`}
              tone="info"
              hint="Usable supplied text divided by the unique selected records in this filter. A blank call transcript or a meeting with no nonblank turn does not count."
              onClick={() => openConversations({ text: "usable" })}
            />
            <Metric
              label="Needs review"
              value={t.needs_review}
              sub={`${t.awaiting_text} awaiting text`}
              tone="warning"
              hint="Records whose review state is needs_review, plus records still awaiting usable text. Reviewed records are excluded."
              onClick={() => openConversations({ review_state: "needs_review" })}
            />
            <Metric
              label="Manual overrides"
              value={t.manual_overrides}
              sub={`${t.route_assignments} route assignments`}
              tone="success"
              hint="Effective routes set by a manager, kept separately from the automated suggestion. Route assignments can exceed records because a conversation can hold several routes."
              onClick={() => openConversations({ override: "yes" })}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <Card className="p-4">
              <SectionHeader
                icon={<CalendarDays className="h-4 w-4" />}
                title="Activity by day"
                description="Calls grouped on started_at, meetings on starts_at, converted to Asia/Kolkata. Selected records only."
                action={<Badge tone="neutral">{metrics.reporting.date}</Badge>}
              />
              <div className="mt-4 h-[210px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={metrics.activity_by_day} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid stroke="#eef0f4" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, borderColor: "#e2e8f0" }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="calls" name="Calls" stackId="a" fill="#2549d8" radius={[0, 0, 0, 0]} maxBarSize={64} />
                    <Bar dataKey="meetings" name="Meetings" stackId="a" fill="#93b0f5" radius={[3, 3, 0, 0]} maxBarSize={64} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-[11.5px] leading-4 text-slate-500">
                All supplied activity falls on one local date, so a date filter alone would not be useful; use
                the person and source-type filters above.
              </p>
            </Card>

            <Card className="p-4">
              <SectionHeader
                icon={<BarChart3 className="h-4 w-4" />}
                title="Routing assignments"
                description={`Effective routes across ${t.records} records. ${t.multi_route_records} record(s) carry more than one route, so assignments (${t.route_assignments}) can exceed records.`}
              />
              <div className="mt-4 h-[246px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={routeData} layout="vertical" margin={{ top: 0, right: 12, left: 8, bottom: 0 }}>
                    <CartesianGrid stroke="#eef0f4" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={132}
                      tick={{ fontSize: 11, fill: "#475569" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, borderColor: "#e2e8f0" }} />
                    <Bar dataKey="count" radius={[0, 3, 3, 0]} maxBarSize={18} name="Effective routes">
                      {routeData.map((entry, index) => (
                        <Cell key={entry.name} fill={ROUTE_COLORS[index % ROUTE_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card className="p-4">
              <SectionHeader
                icon={<PhoneCall className="h-4 w-4" />}
                title="Call representatives"
                description="Grouped by the caller on the call record. No staff directory or performance ranking is supplied."
              />
              <PeopleTable
                rows={metrics.call_reps.map((rep) => ({
                  name: rep.name,
                  primary: rep.calls,
                  primaryLabel: "calls",
                  usable: rep.usable_text,
                }))}
                onSelect={(name) => openConversations({ person: name, source_type: "call" })}
                emptyLabel="No calls in this filter."
              />
              {metrics.unassigned.calls > 0 ? (
                <p className="mt-2 text-[11.5px] text-slate-500">
                  {metrics.unassigned.calls} call(s) have no representative recorded.
                </p>
              ) : null}
            </Card>

            <Card className="p-4">
              <SectionHeader
                icon={<Video className="h-4 w-4" />}
                title="Meeting organisers"
                description="Presented separately from callers. An organiser is not automatically a salesperson or an attendee."
              />
              <PeopleTable
                rows={metrics.meeting_organisers.map((org) => ({
                  name: org.name,
                  primary: org.meetings,
                  primaryLabel: "meetings",
                  usable: org.usable_text,
                }))}
                onSelect={(name) => openConversations({ person: name, source_type: "meeting" })}
                emptyLabel="No meetings in this filter."
              />
              {metrics.unassigned.meetings > 0 ? (
                <p className="mt-2 text-[11.5px] text-slate-500">
                  {metrics.unassigned.meetings} meeting(s) have no organiser recorded.
                </p>
              ) : null}
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="p-4 lg:col-span-2">
              <SectionHeader
                title="Coverage by source type"
                description="The same rule is applied inside each type, with its own denominator."
              />
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <CoverageBar
                  label="Calls"
                  usable={t.usable_calls}
                  total={t.calls}
                  hint="A usable call transcript is nonblank text in payload.transcript."
                  onClick={() => openConversations({ source_type: "call", text: "usable" })}
                />
                <CoverageBar
                  label="Meetings"
                  usable={t.usable_meetings}
                  total={t.meetings}
                  hint="A usable meeting transcript has at least one nonblank turn, even if has_transcript is true."
                  onClick={() => openConversations({ source_type: "meeting", text: "usable" })}
                />
              </div>
              <div className="mt-4 rounded-md border border-slate-200 bg-slate-50/70 px-3 py-2.5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[12px] font-medium text-slate-700">Source-reported call connection</p>
                    <p className="mt-0.5 text-[11.5px] leading-4 text-slate-500">
                      {metrics.connection.connected} connected · {metrics.connection.disconnected} not connected ·{" "}
                      {metrics.connection.unknown} unknown. Rate uses {metrics.connection.denominator} calls with a
                      non-null flag, not all {metrics.connection.calls_total} calls.
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-[22px] font-semibold text-slate-900">{pct(metrics.connection.rate_pct)}</div>
                    <div className="text-[10.5px] text-slate-500">stored classification</div>
                  </div>
                </div>
              </div>
              {metrics.source_outcomes.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {metrics.source_outcomes.map((outcome) => (
                    <Badge key={outcome.outcome} tone="muted">
                      {outcome.outcome}: {outcome.count}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </Card>

            <Card className="p-4">
              <SectionHeader
                icon={<CheckCircle2 className="h-4 w-4" />}
                title="Review states"
                description="Every record has an intake state, including those with no usable text."
              />
              <ul className="mt-3 divide-y divide-slate-100">
                {metrics.review_states.map((state) => (
                  <li key={state.state}>
                    <button
                      type="button"
                      onClick={() => openConversations({ review_state: state.state })}
                      className="flex w-full items-center justify-between gap-2 py-2 text-left hover:text-indigo-700"
                    >
                      <span className="text-[12.5px] text-slate-700">{state.label}</span>
                      <span className="text-[13px] font-semibold text-slate-900">{state.count}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <div className="mt-3 border-t border-slate-100 pt-3">
                <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
                  <Users className="h-3.5 w-3.5" /> Analysis origins
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {metrics.analysis_origin.map((origin) => (
                    <Badge key={origin.origin} tone={origin.origin === "human_assisted" ? "accent" : origin.origin === "pre_generated" ? "info" : "muted"}>
                      {origin.origin.replace("_", " ")}: {origin.count}
                    </Badge>
                  ))}
                </div>
              </div>
            </Card>
          </div>

          <p className={cx("text-[11.5px] leading-5 text-slate-400")}>
            This is a deliberately selected sample of 44 records, not a whole-team day or a representative
            performance measurement. No pipeline value, revenue, deal outcome or account link is inferred.
          </p>
        </>
      )}
    </div>
  );
}

function PeopleTable({
  rows,
  onSelect,
  emptyLabel,
}: {
  rows: { name: string; primary: number; primaryLabel: string; usable: number }[];
  onSelect: (name: string) => void;
  emptyLabel: string;
}) {
  if (rows.length === 0) return <p className="mt-4 text-[12.5px] text-slate-500">{emptyLabel}</p>;
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="table-compact w-full">
        <thead>
          <tr className="border-b border-slate-200 text-left">
            <th className="py-1.5 pr-2 font-semibold">Person</th>
            <th className="py-1.5 pr-2 text-right font-semibold">Records</th>
            <th className="py-1.5 text-right font-semibold">With text</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.name} className="hover:bg-slate-50">
              <td className="py-1.5 pr-2">
                <button
                  type="button"
                  onClick={() => onSelect(row.name)}
                  className="max-w-[190px] truncate text-left font-medium text-indigo-700 hover:underline"
                  title={row.name}
                >
                  {row.name}
                </button>
              </td>
              <td className="py-1.5 pr-2 text-right tabular-nums text-slate-700">
                {row.primary} <span className="text-[11px] text-slate-400">{row.primaryLabel}</span>
              </td>
              <td className="py-1.5 text-right tabular-nums text-slate-700">{row.usable}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CoverageBar({
  label,
  usable,
  total,
  hint,
  onClick,
}: {
  label: string;
  usable: number;
  total: number;
  hint: string;
  onClick: () => void;
}) {
  const ratio = total ? Math.round((usable / total) * 100) : 0;
  return (
    <button type="button" onClick={onClick} className="rounded-md border border-slate-200 p-3 text-left hover:bg-slate-50" title={hint}>
      <div className="flex items-baseline justify-between">
        <span className="text-[12px] font-medium text-slate-700">{label}</span>
        <span className="text-[15px] font-semibold text-slate-900">{ratio}%</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-indigo-600" style={{ width: `${ratio}%` }} />
      </div>
      <p className="mt-1.5 text-[11px] text-slate-500">
        {usable} of {total} {label.toLowerCase()} have usable supplied text
      </p>
    </button>
  );
}
