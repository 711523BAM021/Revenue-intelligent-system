import {
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileWarning,
  History,
  Quote,
  RotateCcw,
  Save,
  ShieldQuestion,
  Sparkles,
  Target,
  UserCheck,
} from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  KeyValue,
  Loading,
  SectionHeader,
} from "../components/ui";
import { api } from "../lib/api";
import {
  cx,
  fmtDateTime,
  fmtDuration,
  freshnessTone,
  originTone,
  reviewTone,
  routeTone,
  stateLabel,
} from "../lib/format";
import type { Evidence, RecordDetail as RecordDetailType, RouteDef } from "../lib/types";

export function ConversationDetail() {
  const { sourceType = "", sourceId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [record, setRecord] = useState<RecordDetailType | null>(null);
  const [routes, setRoutes] = useState<RouteDef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState<Evidence | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api
      .record(sourceType, sourceId)
      .then((data) => {
        setRecord(data);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [sourceType, sourceId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.meta().then((meta) => setRoutes(meta.routes)).catch(() => undefined);
  }, []);

  const routeMap = useMemo(() => new Map(routes.map((route) => [route.key, route])), [routes]);

  if (loading && !record) return <Loading label="Loading conversation" />;
  if (error && !record) return <ErrorState message={error} onRetry={load} />;
  if (!record) return null;

  const content = record.analysis?.content;
  const backSearch = searchParams.toString();

  const act = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    setNotice(null);
    try {
      await fn();
      setNotice(message);
      load();
    } catch (err) {
      setNotice((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 text-[12px] text-slate-500">
        <button
          type="button"
          onClick={() => navigate(`/conversations${backSearch ? `?${backSearch}` : ""}`)}
          className="inline-flex items-center gap-1 hover:text-indigo-700"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Conversations
        </button>
        <ChevronRight className="h-3 w-3 text-slate-300" />
        <span className="font-medium text-slate-700">{record.record_ref}</span>
      </div>

      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cx(
                "inline-flex h-6 items-center rounded px-1.5 text-[11px] font-semibold uppercase",
                record.source_type === "call" ? "bg-indigo-50 text-indigo-700" : "bg-teal-50 text-teal-700",
              )}
            >
              {record.record_ref}
            </span>
            <Badge tone="neutral">{record.source_type}</Badge>
            <Badge tone={reviewTone(record.review_state)}>{record.review_label}</Badge>
            {record.manual_override ? <Badge tone="accent">Manual override</Badge> : null}
            <Badge tone="muted">Revision {record.applied_revision}</Badge>
          </div>
          <h1 className="mt-2 max-w-3xl text-[22px] font-semibold leading-tight tracking-tight text-slate-900">
            {record.title ?? `${record.source_type === "call" ? "Call" : "Meeting"} ${record.record_ref}`}
          </h1>
          <p className="mt-1 text-[12.5px] text-slate-500">
            {fmtDateTime(record.started_at_local)} ·{" "}
            {record.owner_name ? `${record.owner_role_label}: ${record.owner_name}` : `${record.owner_role_label}: not supplied`}
            {record.duration_seconds ? ` · source duration ${fmtDuration(record.duration_seconds)}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => load()} disabled={loading}>Refresh</Button>
          {record.has_usable_text && record.analysis ? (
            <Button
              onClick={() => act(() => api.markPending(sourceType, sourceId), "Analysis marked pending review.")}
              disabled={busy}
            >
              <ShieldQuestion className="h-3.5 w-3.5" /> Mark analysis pending
            </Button>
          ) : null}
        </div>
      </header>

      {notice ? (
        <div className="rounded-md border border-indigo-200 bg-indigo-50 px-3 py-2 text-[12.5px] text-indigo-800">
          {notice}
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <Card className="p-4">
            <SectionHeader
              icon={<Sparkles className="h-4 w-4" />}
              title="Analysis"
              description={
                record.analysis
                  ? `${record.analysis.origin_label} · written against source revision ${record.analysis.source_revision}`
                  : "No substantive analysis exists for this record."
              }
              action={
                record.analysis ? (
                  <div className="flex flex-wrap gap-1.5">
                    <Badge tone={freshnessTone(record.analysis_freshness)}>{record.analysis_freshness_label}</Badge>
                    <Badge tone={originTone(record.analysis.origin)}>{record.analysis.origin_label}</Badge>
                  </div>
                ) : (
                  <Badge tone="muted">Intake only</Badge>
                )
              }
            />

            {record.analysis_freshness === "stale" || record.analysis_freshness === "pending_review" ? (
              <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] leading-5 text-amber-900">
                <strong className="font-semibold">Source text changed.</strong>{" "}
                {record.analysis_freshness === "stale"
                  ? "This analysis was written against an earlier revision and has not been re-read against the new text. It is preserved rather than replaced because it contains manager judgment."
                  : "This analysis is awaiting manager confirmation against the current source text."}
              </div>
            ) : null}

            {content ? (
              <div className="mt-4 space-y-4">
                <Block title="What happened">{content.summary}</Block>
                <Block title="Why it matters">{content.why_it_matters}</Block>

                <div>
                  <h3 className="label-xs mb-1.5">Supporting evidence</h3>
                  <ul className="space-y-1.5">
                    {content.evidence.map((item, index) => (
                      <li key={`${item.quote}-${index}`}>
                        <button
                          type="button"
                          onClick={() => setFocus(item)}
                          className="group flex w-full items-start gap-2 rounded-md border border-slate-200 px-2.5 py-2 text-left hover:border-indigo-200 hover:bg-indigo-50/40"
                        >
                          <Quote className="mt-0.5 h-3 w-3 shrink-0 text-slate-300 group-hover:text-indigo-500" />
                          <span className="min-w-0">
                            <span className="block text-[12.5px] leading-5 text-slate-800">“{item.quote}”</span>
                            <span className="mt-0.5 block text-[11px] text-slate-500">
                              {item.kind === "turn" ? `Turn ${item.turn}` : "Call transcript"}
                              {item.note ? ` · ${item.note}` : ""}
                            </span>
                          </span>
                        </button>
                      </li>
                    ))}
                    {content.evidence.length === 0 ? (
                      <li className="text-[12px] text-slate-500">No transcript passage was cited for this analysis.</li>
                    ) : null}
                  </ul>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <ListBlock title="Risks and blockers" items={content.risks} />
                  <ListBlock title="Opportunities" items={content.opportunities} />
                </div>
                <div>
                  <h3 className="label-xs mb-1.5">What the evidence does not establish</h3>
                  <ListBlock items={content.uncertainties} />
                </div>

                <div className="rounded-md border border-slate-200 bg-slate-50/60 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-[12px] font-semibold uppercase tracking-wide text-slate-500">Recommended next action</h3>
                      <p className="mt-1 text-[13px] leading-5 text-slate-800">{content.next_action}</p>
                    </div>
                    <UserCheck className="h-4 w-4 shrink-0 text-slate-400" />
                  </div>
                  <div className="mt-2 border-t border-slate-200 pt-2 text-[12px] text-slate-600">
                    <span className="font-medium text-slate-700">Owner: </span>
                    {content.action_owner ?? "not supported by the source; manager to assign"}
                    {content.owner_basis ? <span className="text-slate-500"> — {content.owner_basis}</span> : null}
                  </div>
                </div>

                {record.analysis?.author === "manager" ? (
                  <p className="text-[11.5px] text-slate-500">
                    This analysis was written by a manager in the application. The original is kept in revision history.
                  </p>
                ) : (
                  <p className="text-[11.5px] text-slate-500">
                    {record.analysis?.origin === "pre_generated"
                      ? "This analysis was pre-generated offline from the supplied text; the application did not call a model."
                      : "This analysis was produced by deterministic routing rules, not read by an analyst."}
                  </p>
                )}
              </div>
            ) : (
              <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
                <div className="flex items-start gap-2">
                  <FileWarning className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                  <div>
                    <p className="text-[13px] font-medium text-slate-800">No usable supplied conversation text</p>
                    <p className="mt-0.5 text-[12px] leading-5 text-slate-600">
                      {record.unavailable_reason ??
                        "This record arrived without a call transcript or with no nonblank meeting turns."}{" "}
                      No summary, outcome or next action is invented for it. The record keeps an intake state until text
                      is supplied through a later delivery.
                    </p>
                    <p className="mt-1 text-[11.5px] text-slate-500">
                      Missing text is not evidence that the conversation failed or did not happen.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </Card>

          <Card className="p-4">
            <SectionHeader
              icon={<Target className="h-4 w-4" />}
              title="Routing"
              description="The automated suggestion and the manager's decision are stored separately. A manual override always wins until it is reset."
            />
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-slate-200 p-3">
                <div className="label-xs">Automated suggestion</div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {record.suggested_routes.map((route) => (
                    <Badge key={route} tone={routeTone(routeMap.get(route)?.tone ?? "neutral")}>
                      {routeMap.get(route)?.label ?? route}
                    </Badge>
                  ))}
                </div>
                <p className="mt-2 text-[11.5px] leading-5 text-slate-500">
                  {record.routing_method_label}. {record.routing_rationale}
                </p>
              </div>
              <div className={cx("rounded-md border p-3", record.manual_override ? "border-indigo-200 bg-indigo-50/40" : "border-slate-200")}>
                <div className="label-xs">Current effective route</div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {record.effective_routes.map((route) => (
                    <Badge key={route} tone={routeTone(routeMap.get(route)?.tone ?? "neutral")}>
                      {routeMap.get(route)?.label ?? route}
                    </Badge>
                  ))}
                </div>
                <p className="mt-2 text-[11.5px] leading-5 text-slate-500">
                  {record.manual_override
                    ? `Set by a manager${record.override?.reason ? `: “${record.override.reason}”` : "."}`
                    : "Following the automated suggestion; no manual override."}
                </p>
              </div>
            </div>

            {record.routing_trace?.length ? (
              <div className="mt-3 rounded-md border border-slate-200">
                <div className="border-b border-slate-200 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Routing trace
                </div>
                <ul className="divide-y divide-slate-100">
                  {record.routing_trace.map((item, index) => (
                    <li key={`${item.rule}-${index}`} className="px-3 py-1.5 text-[12px]">
                      <span className="font-mono text-[11px] text-indigo-700">{item.rule}</span>
                      <span className="text-slate-400"> → </span>
                      <span className="font-medium text-slate-700">{routeMap.get(item.outcome as never)?.label ?? stateLabel(item.outcome)}</span>
                      <span className="block text-[11.5px] text-slate-500">{item.detail}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <RouteEditor
              record={record}
              routes={routes}
              busy={busy}
              onSave={(selected, reason) =>
                act(() => api.setOverride(sourceType, sourceId, selected, reason), "Manual route saved.")
              }
              onReset={() => act(() => api.resetOverride(sourceType, sourceId), "Manual override reset to the automated suggestion.")}
            />
          </Card>

          <Card className="p-4">
            <SectionHeader
              icon={<CheckCircle2 className="h-4 w-4" />}
              title="Manager review"
              description="Record the decision and its reason. Review state is independent of routing."
              action={<Badge tone={reviewTone(record.review_state)}>{record.review_label}</Badge>}
            />
            <ReviewEditor
              record={record}
              busy={busy}
              onSave={(state, note) => act(() => api.setReview(sourceType, sourceId, state, note), "Review state saved.")}
            />
            {record.review_note ? (
              <p className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-[11.5px] leading-5 text-slate-600">
                <span className="font-medium text-slate-700">Current note: </span>
                {record.review_note}
              </p>
            ) : null}
            {record.has_usable_text ? (
              <HumanAnalysisEditor
                record={record}
                busy={busy}
                onSave={(payload) => act(() => api.saveAnalysis(sourceType, sourceId, payload), "Manager-authored analysis saved.")}
              />
            ) : null}
          </Card>

          <TranscriptCard record={record} focus={focus} />
        </div>

        <aside className="space-y-4">
          <Card className="p-4">
            <SectionHeader title="Source metadata" />
            <dl className="mt-2 divide-y divide-slate-100">
              <KeyValue label="Record reference">{record.record_ref}</KeyValue>
              <KeyValue label="Source type">{record.source_type}</KeyValue>
              <KeyValue label="Source ID">
                <code className="break-all rounded bg-slate-100 px-1 py-0.5 text-[11px]">{record.source_id}</code>
              </KeyValue>
              <KeyValue label="Applied revision">
                {record.applied_revision} <span className="text-slate-400">(first seen {record.first_revision})</span>
              </KeyValue>
              <KeyValue label="Started">{fmtDateTime(record.started_at_local)}</KeyValue>
              <KeyValue label="Activity date">{record.activity_date ?? "Not supplied"}</KeyValue>
              <KeyValue label={record.owner_role_label}>{record.owner_name ?? "Not supplied"}</KeyValue>
              {record.source_type === "call" ? (
                <>
                  <KeyValue label="Direction">{record.direction ?? "Not supplied"}</KeyValue>
                  <KeyValue label="Source duration">{fmtDuration(record.duration_seconds)}</KeyValue>
                  <KeyValue label="Source-reported outcome">{record.source_outcome ?? "Not supplied"}</KeyValue>
                  <KeyValue label="is_connected">
                    {record.is_connected === null ? "Unknown (null)" : record.is_connected ? "true" : "false"}
                  </KeyValue>
                  <KeyValue label="is_conversation">
                    {record.is_conversation === null ? "Unknown (null)" : record.is_conversation ? "true" : "false"}
                  </KeyValue>
                </>
              ) : (
                <>
                  <KeyValue label="Recording status">{record.recording_status ?? "Not supplied"}</KeyValue>
                  <KeyValue label="has_transcript flag">
                    {record.has_transcript_flag === null ? "Unknown" : String(record.has_transcript_flag)}
                  </KeyValue>
                  <KeyValue label="Usable turns">{record.turns?.length ?? 0}</KeyValue>
                </>
              )}
              <KeyValue label="Usable text">{record.has_usable_text ? "Yes" : "No"}</KeyValue>
            </dl>
          </Card>

          <Card className="p-4">
            <SectionHeader title="Analysis state" />
            <dl className="mt-2 divide-y divide-slate-100">
              <KeyValue label="Freshness">
                <Badge tone={freshnessTone(record.analysis_freshness)}>{record.analysis_freshness_label}</Badge>
              </KeyValue>
              <KeyValue label="Origin">{record.analysis?.origin_label ?? "None"}</KeyValue>
              <KeyValue label="Written for revision">{record.analysis?.source_revision ?? "—"}</KeyValue>
              <KeyValue label="Last updated">{record.analysis ? fmtDateTime(record.analysis.updated_at) : "—"}</KeyValue>
              <KeyValue label="Review state">
                <Badge tone={reviewTone(record.review_state)}>{record.review_label}</Badge>
              </KeyValue>
            </dl>
            {record.archived_analyses.length > 0 ? (
              <div className="mt-3 border-t border-slate-100 pt-3">
                <div className="label-xs mb-1.5">Superseded analyses</div>
                <ul className="space-y-1 text-[11.5px] text-slate-600">
                  {record.archived_analyses.map((item, index) => (
                    <li key={index}>
                      Revision {item.source_revision} · {item.origin.replace("_", " ")} · {fmtDateTime(item.archived_at)}
                      {item.reason ? <span className="block text-[11px] text-slate-400">{item.reason}</span> : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </Card>

          <Card className="p-4">
            <SectionHeader icon={<History className="h-4 w-4" />} title="Revision and import history" />
            <ul className="mt-3 space-y-2.5">
              {record.import_events.slice(0, 6).map((event) => (
                <li key={`${event.batch_id}-${event.imported_at}`} className="border-l-2 border-slate-200 pl-2.5">
                  <div className="text-[12px] font-medium text-slate-700">
                    Rev {event.revision} · {event.filename}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {fmtDateTime(event.imported_at)} · {event.status}
                  </div>
                  {event.record_actions.length > 0 ? (
                    <div className="mt-0.5 text-[11px] text-slate-500">
                      {event.record_actions.map((action, index) => (
                        <span key={index}>
                          {String(action.action)}
                          {action.to_revision ? ` → rev ${String(action.to_revision)}` : ""}
                          {action.text_changed ? " (text changed)" : ""}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
            <div className="mt-3 border-t border-slate-100 pt-3">
              <div className="label-xs mb-1.5">Record events</div>
              <ul className="space-y-1 text-[11.5px] text-slate-600">
                {record.history.slice(0, 6).map((event, index) => (
                  <li key={index} className="flex items-start gap-1.5">
                    <Clock className="mt-0.5 h-3 w-3 shrink-0 text-slate-300" />
                    <span>
                      {stateLabel(event.kind)} · {fmtDateTime(event.created_at)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="label-xs mb-1">{title}</h3>
      <p className="text-[13.5px] leading-6 text-slate-800">{children}</p>
    </div>
  );
}

function ListBlock({ title, items }: { title?: string; items: string[] }) {
  return (
    <div>
      {title ? <h3 className="label-xs mb-1.5">{title}</h3> : null}
      {items.length ? (
        <ul className="list-disc space-y-0.5 pl-4 text-[12.5px] leading-5 text-slate-700">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="text-[12px] text-slate-400">None recorded.</p>
      )}
    </div>
  );
}

function RouteEditor({
  record,
  routes,
  busy,
  onSave,
  onReset,
}: {
  record: RecordDetailType;
  routes: RouteDef[];
  busy: boolean;
  onSave: (routes: string[], reason: string) => void;
  onReset: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>(record.effective_routes);
  const [reason, setReason] = useState(record.override?.reason ?? "");

  useEffect(() => {
    setSelected(record.effective_routes);
    setReason(record.override?.reason ?? "");
  }, [record.effective_routes, record.override?.reason]);

  const toggle = (key: string) => {
    setSelected((current) =>
      current.includes(key) ? current.filter((value) => value !== key) : [...current, key],
    );
  };

  if (!open) {
    return (
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" onClick={() => setOpen(true)}>
          Correct route
        </Button>
        {record.manual_override ? (
          <Button size="sm" variant="danger" onClick={onReset} disabled={busy}>
            <RotateCcw className="h-3.5 w-3.5" /> Reset override
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-md border border-indigo-200 bg-indigo-50/30 p-3">
      <div className="flex items-center justify-between">
        <h3 className="text-[12px] font-semibold text-slate-800">Set the effective route</h3>
        <button type="button" className="text-[11.5px] text-slate-500 hover:underline" onClick={() => setOpen(false)}>
          Close
        </button>
      </div>
      <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
        {routes.map((route) => (
          <label
            key={route.key}
            className={cx(
              "flex cursor-pointer items-start gap-2 rounded border px-2 py-1.5 text-[12px]",
              selected.includes(route.key) ? "border-indigo-300 bg-white" : "border-transparent bg-white/50",
            )}
          >
            <input
              type="checkbox"
              checked={selected.includes(route.key)}
              onChange={() => toggle(route.key)}
              className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300 text-indigo-700"
            />
            <span>
              <span className="font-medium text-slate-800">{route.label}</span>
              <span className="mt-0.5 block text-[10.5px] leading-4 text-slate-500">{route.description}</span>
            </span>
          </label>
        ))}
      </div>
      <label className="mt-2 block">
        <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Correction reason
        </span>
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={2}
          placeholder="Why are you changing the automated suggestion?"
          className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-[12.5px]"
        />
      </label>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="primary"
          disabled={busy || selected.length === 0 || reason.trim().length < 3}
          onClick={() => onSave(selected, reason.trim())}
        >
          <Save className="h-3.5 w-3.5" /> Save manual route
        </Button>
        <Button size="sm" onClick={() => setOpen(false)}>Cancel</Button>
        <span className="self-center text-[11px] text-slate-500">A reason is required so the decision is auditable.</span>
      </div>
    </div>
  );
}

function ReviewEditor({
  record,
  busy,
  onSave,
}: {
  record: RecordDetailType;
  busy: boolean;
  onSave: (state: string, note: string) => void;
}) {
  const [state, setState] = useState(record.review_state);
  const [note, setNote] = useState(record.review_note ?? "");

  useEffect(() => {
    setState(record.review_state);
    setNote(record.review_note ?? "");
  }, [record.review_state, record.review_note]);

  return (
    <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
      <label className="sm:w-52">
        <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">Review state</span>
        <select
          value={state}
          onChange={(event) => setState(event.target.value)}
          className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-[12.5px]"
        >
          <option value="unreviewed">Not yet reviewed</option>
          <option value="needs_review">Needs review</option>
          <option value="reviewed">Reviewed</option>
          <option value="awaiting_text" disabled={record.has_usable_text}>
            Awaiting usable text
          </option>
        </select>
      </label>
      <label className="flex-1">
        <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Short note (optional)
        </span>
        <input
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="What did you check or decide?"
          className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-[12.5px]"
        />
      </label>
      <Button onClick={() => onSave(state, note)} disabled={busy} size="sm">
        Save review
      </Button>
    </div>
  );
}

function HumanAnalysisEditor({
  record,
  busy,
  onSave,
}: {
  record: RecordDetailType;
  busy: boolean;
  onSave: (payload: {
    summary: string;
    why_it_matters: string;
    evidence: Evidence[];
    risks: string[];
    opportunities: string[];
    uncertainties: string[];
    next_action: string;
    action_owner: string | null;
    owner_basis: string | null;
  }) => void;
}) {
  const content = record.analysis?.content;
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState(content?.summary ?? "");
  const [why, setWhy] = useState(content?.why_it_matters ?? "");
  const [next, setNext] = useState(content?.next_action ?? "");
  const [owner, setOwner] = useState(content?.action_owner ?? "");
  const [basis, setBasis] = useState(content?.owner_basis ?? "");
  const [risks, setRisks] = useState((content?.risks ?? []).join("\n"));
  const [uncertainties, setUncertainties] = useState((content?.uncertainties ?? []).join("\n"));
  const [quotes, setQuotes] = useState(
    (content?.evidence ?? [])
      .map((item) => (item.kind === "turn" ? `${item.turn} | ${item.quote}` : item.quote))
      .join("\n"),
  );

  const parseEvidence = (): Evidence[] =>
    quotes
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        if (record.source_type === "meeting" && line.includes("|")) {
          const [turn, ...rest] = line.split("|");
          return { kind: "turn" as const, turn: Number(turn.trim()), quote: rest.join("|").trim(), note: "Manager-supplied evidence" };
        }
        return { kind: "quote" as const, quote: line, note: "Manager-supplied evidence" };
      });

  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      {!open ? (
        <Button size="sm" onClick={() => setOpen(true)}>
          {record.analysis?.origin === "human_assisted" ? "Edit manager analysis" : "Write human-assisted analysis"}
        </Button>
      ) : (
        <div className="space-y-2.5">
          <p className="text-[11.5px] leading-5 text-slate-500">
            This replaces the displayed analysis with manager-authored content and keeps the previous version in
            revision history. Suggested routes stay controlled by the routing panel above.
          </p>
          <Area label="Summary" value={summary} onChange={setSummary} rows={3} />
          <Area label="Why it matters" value={why} onChange={setWhy} rows={2} />
          <div className="grid gap-2 sm:grid-cols-2">
            <Area label="Risks (one per line)" value={risks} onChange={setRisks} rows={2} />
            <Area label="Uncertainties (one per line)" value={uncertainties} onChange={setUncertainties} rows={2} />
          </div>
          <Area label="Next action" value={next} onChange={setNext} rows={2} />
          <div className="grid gap-2 sm:grid-cols-2">
            <Area label="Action owner (only if supported)" value={owner} onChange={setOwner} rows={1} />
            <Area label="Ownership basis" value={basis} onChange={setBasis} rows={1} />
          </div>
          <Area
            label={
              record.source_type === "meeting"
                ? "Evidence (one per line: turn number | exact quote)"
                : "Evidence (exact call quotes, one per line)"
            }
            value={quotes}
            onChange={setQuotes}
            rows={3}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="primary"
              disabled={busy || summary.trim().length < 10}
              onClick={() =>
                onSave({
                  summary: summary.trim(),
                  why_it_matters: why.trim(),
                  evidence: parseEvidence(),
                  risks: risks.split("\n").map((item) => item.trim()).filter(Boolean),
                  opportunities: content?.opportunities ?? [],
                  uncertainties: uncertainties.split("\n").map((item) => item.trim()).filter(Boolean),
                  next_action: next.trim(),
                  action_owner: owner.trim() || null,
                  owner_basis: basis.trim() || null,
                })
              }
            >
              <Save className="h-3.5 w-3.5" /> Save manager analysis
            </Button>
            <Button size="sm" onClick={() => setOpen(false)}>Cancel</Button>
            <span className="self-center text-[11px] text-slate-400">
              Saved as “manager-authored”, distinct from the automated analysis.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function Area({
  label,
  value,
  onChange,
  rows,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows: number;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <textarea
        value={value}
        rows={rows}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-[12.5px] leading-5"
      />
    </label>
  );
}

function TranscriptCard({ record, focus }: { record: RecordDetailType; focus: Evidence | null }) {
  const [query, setQuery] = useState("");

  const highlight = (text: string) => {
    const targets = [focus?.quote, query].filter((value): value is string => Boolean(value && value.length > 2));
    if (targets.length === 0) return text;
    const pattern = new RegExp(`(${targets.map((value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
    const parts = text.split(pattern);
    return parts.map((part, index) =>
      targets.some((target) => part.toLowerCase() === target.toLowerCase()) ? (
        <mark key={index}>{part}</mark>
      ) : (
        <Fragment key={index}>{part}</Fragment>
      ),
    );
  };

  return (
    <Card className="p-4">
      <SectionHeader
        title={record.source_type === "meeting" ? "Supplied meeting turns" : "Supplied call transcript"}
        description={
          record.source_type === "meeting"
            ? "Turn numbers are 1-based positions in the supplied turns array. Timecodes locate the excerpt; they are not identities."
            : "Adapted call text. There are no trustworthy turn timings for calls, so evidence cites a short exact quotation only."
        }
        action={
          record.has_usable_text ? (
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Find in text"
              aria-label="Find in transcript"
              className="w-44 rounded-md border border-slate-300 px-2 py-1 text-[12px]"
            />
          ) : null
        }
      />
      {!record.has_usable_text ? (
        <p className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-3 text-[12.5px] leading-5 text-slate-600">
          No transcript or usable meeting turns were supplied in the current revision.
          {record.unavailable_reason ? ` Source note: ${record.unavailable_reason}` : ""}
        </p>
      ) : record.source_type === "meeting" ? (
        <ol className="mt-3 space-y-2">
          {(record.turns ?? []).map((turn) => {
            const isFocused = focus?.kind === "turn" && focus.turn === turn.turn;
            return (
              <li
                key={turn.turn}
                className={cx(
                  "rounded-md border px-3 py-2",
                  isFocused ? "border-amber-300 bg-amber-50/60" : "border-slate-200",
                )}
              >
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                  <span className="inline-flex h-5 min-w-5 items-center justify-center rounded bg-slate-100 px-1 font-semibold text-slate-700">
                    {turn.turn}
                  </span>
                  <span className="font-medium text-slate-700">{turn.speaker ?? "Speaker not supplied"}</span>
                  {turn.timecode ? <span className="font-mono text-slate-400">{turn.timecode}</span> : null}
                </div>
                <p className="mt-1 text-[13px] leading-6 text-slate-800">{highlight(turn.text)}</p>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="mt-3 whitespace-pre-line rounded-md border border-slate-200 px-3 py-3 text-[13px] leading-6 text-slate-800">
          {highlight(record.transcript_text ?? "")}
        </p>
      )}
    </Card>
  );
}
