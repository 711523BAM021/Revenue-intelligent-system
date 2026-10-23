import { AlertTriangle, BookOpen, Database, RotateCcw, ShieldCheck, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, ErrorState, Loading, PageHeader, SectionHeader } from "../components/ui";
import { api } from "../lib/api";
import type { Meta } from "../lib/types";

type QualityData = {
  counts: Record<string, number>;
  lists: Record<string, string[]>;
  unverified_evidence: { record_ref: string; evidence: { quote: string; turn?: number } }[];
  notes: string[];
  metrics_notes: { metric: string; definition: string }[];
};

const COUNT_LABELS: { key: string; label: string; hint: string }[] = [
  { key: "records", label: "Selected records", hint: "Distinct (source_type, source_id) pairs." },
  { key: "usable_text", label: "With usable text", hint: "Nonblank call transcript or at least one nonblank meeting turn." },
  { key: "no_usable_text", label: "No usable text", hint: "Intake state only; no substantive analysis is invented." },
  { key: "text_without_analysis", label: "Text without analysis", hint: "Should be zero for the supplied corpus." },
  { key: "stale_or_pending_analysis", label: "Stale / pending analyses", hint: "Visible flags, never silently shown as current." },
  { key: "unverified_evidence", label: "Unverified citations", hint: "Quotes checked against the current source text at runtime." },
  { key: "missing_owner", label: "Missing caller/organiser", hint: "Role is never inferred from a title." },
  { key: "multi_route_records", label: "Multi-route records", hint: "One conversation can produce several outputs." },
  { key: "meetings_flagged_without_turns", label: "Meetings flagged but empty", hint: "has_transcript=true with zero usable turns is a source condition." },
  { key: "calls_flagged_without_text", label: "Calls flagged but blank", hint: "Source classification disagreeing with supplied text." },
];

export function Quality() {
  const [quality, setQuality] = useState<QualityData | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([api.quality(), api.meta()])
      .then(([qualityData, metaData]) => {
        setQuality(qualityData);
        setMeta(metaData);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const reset = async () => {
    try {
      const result = await api.reset();
      setNotice(result.message);
      load();
    } catch (err) {
      setNotice((err as Error).message);
    }
  };

  if (loading && !quality) return <Loading label="Loading data quality checks" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!quality || !meta) return null;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Data quality / Settings"
        title="What the data can and cannot support"
        description="These checks are computed from the current database. They are diagnostic, not a substitute for reading the conversation."
        actions={
          <>
            <Button onClick={load}>Re-run checks</Button>
            <Button variant="danger" onClick={reset}>
              <RotateCcw className="h-3.5 w-3.5" /> Reset workspace
            </Button>
          </>
        }
      />

      {notice ? (
        <div className="rounded-md border border-indigo-200 bg-indigo-50 px-3 py-2 text-[12.5px] text-indigo-800">
          {notice}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {COUNT_LABELS.map((item) => (
          <Card key={item.key} className="px-3.5 py-3">
            <div className="label-xs" title={item.hint}>{item.label}</div>
            <div className="mt-1 text-[22px] font-semibold text-slate-900">{quality.counts[item.key] ?? 0}</div>
            <p className="mt-0.5 text-[10.5px] leading-4 text-slate-500">{item.hint}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="p-4">
          <SectionHeader
            icon={<AlertTriangle className="h-4 w-4" />}
            title="Anomalies and exceptions"
            description="Record references, so each item can be opened and checked."
          />
          <ul className="mt-3 space-y-2.5">
            {quality.lists.no_usable_text?.length ? (
              <Anomaly label="No usable supplied text" refs={quality.lists.no_usable_text} tone="neutral" />
            ) : null}
            {quality.lists.stale_or_pending_analysis?.length ? (
              <Anomaly label="Analysis marked stale or pending" refs={quality.lists.stale_or_pending_analysis} tone="warning" />
            ) : null}
            {quality.lists.missing_owner?.length ? (
              <Anomaly label="No caller or organiser supplied" refs={quality.lists.missing_owner} tone="muted" />
            ) : null}
            {quality.lists.meetings_flagged_without_turns?.length ? (
              <Anomaly label="has_transcript=true but no usable turns" refs={quality.lists.meetings_flagged_without_turns} tone="warning" />
            ) : null}
            {quality.lists.calls_flagged_without_text?.length ? (
              <Anomaly label="Call flagged as transcribed but text is blank" refs={quality.lists.calls_flagged_without_text} tone="warning" />
            ) : null}
            {quality.lists.multi_route_records?.length ? (
              <Anomaly label="Multiple routes on one record" refs={quality.lists.multi_route_records} tone="info" />
            ) : null}
            {quality.lists.text_without_analysis?.length ? (
              <Anomaly label="Usable text but no analysis" refs={quality.lists.text_without_analysis} tone="danger" />
            ) : null}
          </ul>
          <ul className="mt-3 space-y-1.5 border-t border-slate-100 pt-2.5 text-[11.5px] leading-5 text-slate-600">
            {quality.notes.map((note) => (
              <li key={note} className="flex items-start gap-1.5">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
                {note}
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-4">
          <SectionHeader
            icon={<ShieldCheck className="h-4 w-4" />}
            title="Evidence verification"
            description="Every pre-generated citation is looked up in the current source text on this page load."
          />
          {quality.unverified_evidence.length === 0 ? (
            <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-[12.5px] text-emerald-800">
              All pre-generated citations resolve to the current text. {quality.counts.records} records checked.
            </div>
          ) : (
            <ul className="mt-3 space-y-2">
              {quality.unverified_evidence.map((item, index) => (
                <li key={index} className="rounded-md border border-rose-200 bg-rose-50 px-2.5 py-2 text-[12px] text-rose-800">
                  <strong>{item.record_ref}</strong>
                  {item.evidence.turn ? ` · turn ${item.evidence.turn}` : ""}: “{item.evidence.quote}”
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 rounded-md bg-slate-50 px-3 py-2.5 text-[11.5px] leading-5 text-slate-600">
            <strong className="font-medium text-slate-800">Citation convention.</strong>{" "}
            Meeting evidence cites the source record and a 1-based turn number from the supplied turns array. Call
            evidence cites a short exact quotation; no timecodes are invented for calls. Timecodes locate an excerpt
            and are never treated as identifiers.
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="p-4">
          <SectionHeader icon={<BookOpen className="h-4 w-4" />} title="Metric definitions" description="Shown next to the numbers in the app and repeated in the export." />
          <dl className="mt-3 divide-y divide-slate-100">
            {quality.metrics_notes.map((note) => (
              <div key={note.metric} className="py-2">
                <dt className="text-[12px] font-semibold text-slate-800">{note.metric}</dt>
                <dd className="mt-0.5 text-[11.5px] leading-5 text-slate-600">{note.definition}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card className="p-4">
          <SectionHeader title="Routing definitions" description="The same taxonomy is used by the engine, the exports and the brief." />
          <ul className="mt-3 space-y-2">
            {meta.routes.map((route) => (
              <li key={route.key} className="rounded-md border border-slate-200 px-2.5 py-2">
                <div className="flex items-center justify-between gap-2">
                  <Badge tone={route.tone}>{route.label}</Badge>
                  <code className="text-[10.5px] text-slate-400">{route.key}</code>
                </div>
                <p className="mt-1 text-[11.5px] leading-5 text-slate-600">{route.description}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="p-4">
        <SectionHeader
          icon={<Sparkles className="h-4 w-4" />}
          title="Provenance and settings"
          description="What is pre-generated, what is computed, and what this app deliberately does not claim."
        />
        <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <Provenance
            title="Pre-generated"
            items={[
              "The 18 conversation analyses, the manager-brief narrative, the three findings and the rejected decision.",
              "Authored offline against the supplied text, then loaded read-only. No model is called by the application.",
              "Each analysis records the source revision it was written for.",
            ]}
          />
          <Provenance
            title="Computed at runtime"
            items={[
              "All counts, coverage, denominators, activity grouping, review states, route counts and overrides.",
              "Revision application, analysis freshness and evidence verification against the current text.",
              "Export manifests, zip contents and the pass/fail replay checks.",
            ]}
          />
          <Provenance
            title="Deliberately not claimed"
            items={[
              "Pipeline value, revenue, deal stage, probability or account joins.",
              "Staff roles, salesperson identity on meetings, or performance rankings.",
              "A failed conversation because a transcript is missing.",
            ]}
          />
        </div>
        <div className="mt-4 grid gap-2 rounded-md bg-slate-50 px-3 py-2.5 text-[11.5px] text-slate-600 sm:grid-cols-2">
          <div>
            <span className="font-medium text-slate-700">Reporting period:</span> {meta.reporting_date} ({meta.timezone})
          </div>
          <div>
            <span className="font-medium text-slate-700">Deliveries:</span>{" "}
            {meta.datasets.map((dataset) => `${dataset.filename} ${dataset.exists ? "present" : "missing"}`).join(" · ")}
          </div>
          <div>
            <span className="font-medium text-slate-700">Identity:</span> (source_type, source_id), enforced by a unique constraint
          </div>
          <div>
            <span className="font-medium text-slate-700">Persistence:</span> SQLite via SQLAlchemy; survives browser refresh and restart
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge tone="neutral"><Database className="h-3 w-3" /> {meta.counts.records} records stored</Badge>
          <Badge tone="neutral">{meta.counts.imports} import batches</Badge>
          <Badge tone="neutral">{meta.counts.exports} export runs</Badge>
        </div>
      </Card>
    </div>
  );
}

function Anomaly({ label, refs, tone }: { label: string; refs: string[]; tone: string }) {
  return (
    <li>
      <div className="flex items-center gap-2">
        <Badge tone={tone}>{refs.length}</Badge>
        <span className="text-[12px] text-slate-700">{label}</span>
      </div>
      <p className="mt-1 font-mono text-[10.5px] leading-4 text-slate-500">{refs.join(", ")}</p>
    </li>
  );
}

function Provenance({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <h3 className="text-[12px] font-semibold text-slate-800">{title}</h3>
      <ul className="mt-1.5 space-y-1 text-[11.5px] leading-5 text-slate-600">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-1.5">
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
