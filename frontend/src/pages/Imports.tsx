import {
  AlertTriangle,
  ArrowDownToLine,
  CheckCircle2,
  FlaskConical,
  PlayCircle,
  RotateCcw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, ErrorState, Loading, PageHeader, SectionHeader } from "../components/ui";
import { api } from "../lib/api";
import { cx, fmtDateTime, pct } from "../lib/format";
import type { ImportBatch, Metrics, ReplayResult, RecordSummary } from "../lib/types";

type LogEntry = { at: string; label: string; ok: boolean; detail: string };

export function Imports() {
  const [imports, setImports] = useState<{
    datasets: { dataset: string; filename: string; exists: boolean; bytes: number }[];
    batches: ImportBatch[];
    current: { records: number; revisions: Record<string, number> };
  } | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [m07, setM07] = useState<RecordSummary | null>(null);
  const [replay, setReplay] = useState<ReplayResult | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [replayBusy, setReplayBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [importsData, metricsData, recordsData] = await Promise.all([
        api.imports(),
        api.metrics(),
        api.records({ search: "M07" }),
      ]);
      setImports(importsData);
      setMetrics(metricsData);
      setM07(recordsData.records.find((record) => record.record_ref === "M07") ?? null);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const push = (label: string, ok: boolean, detail: string) => {
    setLog((current) => [{ at: new Date().toISOString(), label, ok, detail }, ...current].slice(0, 12));
  };

  const run = async (key: string, label: string, action: () => Promise<string>) => {
    setBusy(key);
    try {
      const detail = await action();
      push(label, true, detail);
      await refresh();
    } catch (err) {
      push(label, false, (err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const importDataset = (dataset: "initial" | "update", shuffle = false) =>
    run(dataset + (shuffle ? "-shuffle" : ""), `Import ${dataset}${shuffle ? " (shuffled)" : ""}`, async () => {
      const result = await api.importDataset(dataset, shuffle);
      const b = result.batch;
      return `rev ${b.delivery_revision} · inserted ${b.inserted}, updated ${b.updated}, ignored ${b.ignored} · now ${result.metrics.records} records, ${result.metrics.usable_text}/${result.metrics.coverage_denominator} with text`;
    });

  const correctM07 = () =>
    run("m07", "Correct M07 route", async () => {
      if (!m07) throw new Error("M07 is not imported yet. Import the initial delivery first.");
      const updated = await api.setOverride(
        m07.source_type,
        m07.source_id,
        ["customer_success"],
        "Manager: this is a support conversation, not a deal.",
      );
      return `Effective route set to ${updated.effective_route_labels.join(", ")}; suggested remains ${updated.suggested_route_labels.join(", ")}`;
    });

  const runReplay = async () => {
    setReplayBusy(true);
    try {
      const result = await api.replay();
      setReplay(result);
      if (!result.available) push("Replay verification", false, result.errors?.join(" ") ?? "Unavailable");
      else
        push(
          "Replay verification",
          result.summary.failed === 0,
          `${result.summary.passed}/${result.summary.total} checks passed`,
        );
    } catch (err) {
      push("Replay verification", false, (err as Error).message);
    } finally {
      setReplayBusy(false);
    }
  };

  if (!imports && !error) return <Loading label="Loading import state" />;

  const datasetsReady = imports?.datasets.every((dataset) => dataset.exists) ?? false;
  const revisions = imports?.current.revisions ?? {};

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Import History"
        title="Import lab and revision control"
        description="The record identity is (source_type, source_id). A newer revision replaces the whole source payload; equal or older revisions are ignored; manual routing is stored separately."
        actions={
          <>
            <Button onClick={refresh} disabled={Boolean(busy)}>Refresh</Button>
            <Button variant="primary" onClick={runReplay} disabled={replayBusy}>
              <ShieldCheck className="h-3.5 w-3.5" /> {replayBusy ? "Running…" : "Run replay verification"}
            </Button>
          </>
        }
      />

      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      {!datasetsReady ? (
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-[12.5px] leading-5 text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            The supplied delivery files are not both present in <code className="rounded bg-amber-100 px-1">data/</code>.
            Place <code className="rounded bg-amber-100 px-1">01_initial.json</code> and{" "}
            <code className="rounded bg-amber-100 px-1">02_update.json</code> there, then refresh. The engine refuses
            to import a missing or malformed batch rather than guessing.
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-4">
          <Card className="p-4">
            <SectionHeader
              icon={<FlaskConical className="h-4 w-4" />}
              title="Reproduce the required replay"
              description="Run the steps in order. Every number below is read back from the database after the action."
            />
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <StepButton
                index="1"
                title="Reset to a clean state"
                description="Deletes records, analyses, overrides and import history."
                busy={busy === "reset"}
                onClick={() =>
                  run("reset", "Reset workspace", async () => {
                    const result = await api.reset();
                    return result.message;
                  })
                }
                icon={<RotateCcw className="h-3.5 w-3.5" />}
              />
              <StepButton
                index="2"
                title="Import 01_initial.json"
                description="Revision 1 creates the 44 logical records."
                busy={busy === "initial"}
                onClick={() => importDataset("initial")}
                icon={<ArrowDownToLine className="h-3.5 w-3.5" />}
              />
              <StepButton
                index="3"
                title="Repeat initial, shuffled"
                description="Same revision in a different array order must be ignored per record."
                busy={busy === "initial-shuffle"}
                onClick={() => importDataset("initial", true)}
                icon={<ArrowDownToLine className="h-3.5 w-3.5" />}
              />
              <StepButton
                index="4"
                title="Change M07's route"
                description="Manual correction to Customer success, with a reason."
                busy={busy === "m07"}
                onClick={correctM07}
                icon={<PlayCircle className="h-3.5 w-3.5" />}
              />
              <StepButton
                index="5"
                title="Import 02_update.json"
                description="Revision 2 adds M07's transcript without adding a record."
                busy={busy === "update"}
                onClick={() => importDataset("update")}
                icon={<ArrowDownToLine className="h-3.5 w-3.5" />}
              />
              <StepButton
                index="6"
                title="Replay 01_initial.json"
                description="Revision 1 arriving after revision 2 must not overwrite newer information."
                busy={busy === "initial-replay"}
                onClick={() => importDataset("initial")}
                icon={<ArrowDownToLine className="h-3.5 w-3.5" />}
              />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md bg-slate-50 px-3 py-2.5">
              <span className="text-[11.5px] text-slate-600">
                Shortcut for a reviewer: load the final post-update state in one action.
              </span>
              <Button
                size="sm"
                onClick={() =>
                  run("demo", "Load post-update demo state", async () => (await api.demoLoad()).message)
                }
                disabled={busy === "demo" || !datasetsReady}
              >
                {busy === "demo" ? "Loading…" : "Load post-update demo state"}
              </Button>
              <span className="text-[11px] text-slate-400">(resets first, then imports revision 1 and 2)</span>
            </div>
          </Card>

          <Card className="p-4">
            <SectionHeader title="Activity log" description="Results from this browser session, newest first." />
            {log.length === 0 ? (
              <p className="mt-3 text-[12.5px] text-slate-500">No actions yet. Start with step 1 or 2.</p>
            ) : (
              <ul className="mt-2 divide-y divide-slate-100">
                {log.map((entry) => (
                  <li key={`${entry.at}-${entry.label}`} className="flex items-start gap-2 py-2">
                    {entry.ok ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    ) : (
                      <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
                    )}
                    <div className="min-w-0">
                      <div className="text-[12.5px] font-medium text-slate-800">{entry.label}</div>
                      <div className="break-words text-[11.5px] leading-5 text-slate-600">{entry.detail}</div>
                      <div className="text-[10.5px] text-slate-400">{fmtDateTime(entry.at)}</div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="overflow-hidden">
            <div className="border-b border-slate-200 px-4 py-2.5">
              <h2 className="text-[14px] font-semibold text-slate-900">Import batches</h2>
              <p className="mt-0.5 text-[11.5px] text-slate-500">
                Batch ID, delivery revision, timestamp and per-record outcomes.
              </p>
            </div>
            {imports?.batches.length ? (
              <div className="overflow-x-auto">
                <table className="table-compact w-full min-w-[840px]">
                  <thead className="bg-slate-50/80">
                    <tr className="border-b border-slate-200 text-left">
                      <th className="px-3 py-2">Batch</th>
                      <th className="px-3 py-2">File</th>
                      <th className="px-3 py-2">Rev</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2 text-right">Inserted</th>
                      <th className="px-3 py-2 text-right">Updated</th>
                      <th className="px-3 py-2 text-right">Ignored</th>
                      <th className="px-3 py-2">Imported</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {imports.batches.map((batch) => (
                      <tr key={batch.id}>
                        <td className="px-3 py-2 font-mono text-[10.5px] text-slate-500">{batch.batch_id.slice(0, 16)}</td>
                        <td className="px-3 py-2">{batch.filename}</td>
                        <td className="px-3 py-2 tabular-nums">{batch.delivery_revision}</td>
                        <td className="px-3 py-2">
                          <Badge tone={batch.status === "applied" ? "success" : "danger"}>{batch.status}</Badge>
                          {batch.errors.length > 0 ? (
                            <div className="mt-1 text-[10.5px] text-rose-700">{batch.errors[0]}</div>
                          ) : null}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">{batch.inserted}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{batch.updated}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{batch.ignored}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{fmtDateTime(batch.imported_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="px-4 py-4 text-[12.5px] text-slate-500">No imports recorded yet.</p>
            )}
          </Card>

          <Card className="p-4">
            <SectionHeader
              icon={<ShieldCheck className="h-4 w-4" />}
              title="Replay verification"
              description="Executed against a temporary database with the same engine, so it can be run without disturbing saved corrections."
            />
            {!replay ? (
              <p className="mt-3 text-[12.5px] text-slate-500">
                Run the verification to execute reset → initial → shuffle → M07 correction → update → replay and assert
                every contract point.
              </p>
            ) : !replay.available ? (
              <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[12.5px] text-rose-800">
                {replay.errors?.join(" ")}
              </div>
            ) : (
              <div className="mt-3 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={replay.summary.failed === 0 ? "success" : "danger"}>
                    {replay.summary.passed}/{replay.summary.total} checks passed
                  </Badge>
                  <span className="text-[11.5px] text-slate-500">{replay.note}</span>
                </div>
                <div className="overflow-hidden rounded-md border border-slate-200">
                  <table className="table-compact w-full">
                    <thead className="bg-slate-50">
                      <tr className="text-left">
                        <th className="px-3 py-1.5">Check</th>
                        <th className="px-3 py-1.5">Expected</th>
                        <th className="px-3 py-1.5">Actual</th>
                        <th className="px-3 py-1.5">Result</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {replay.checks.map((check) => (
                        <tr key={check.id}>
                          <td className="px-3 py-1.5">{check.label}</td>
                          <td className="max-w-[190px] px-3 py-1.5 font-mono text-[10.5px] text-slate-500">
                            {compact(check.expected)}
                          </td>
                          <td className="max-w-[190px] px-3 py-1.5 font-mono text-[10.5px] text-slate-600">
                            {compact(check.actual)}
                          </td>
                          <td className="px-3 py-1.5">
                            {check.pass ? (
                              <span className="inline-flex items-center gap-1 text-[11.5px] font-medium text-emerald-700">
                                <CheckCircle2 className="h-3.5 w-3.5" /> pass
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-[11.5px] font-medium text-rose-700">
                                <XCircle className="h-3.5 w-3.5" /> fail
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div>
                  <h3 className="label-xs mb-1.5">Observed sequence</h3>
                  <ol className="space-y-2">
                    {replay.steps.map((step) => (
                      <li key={step.title} className="rounded-md border border-slate-200 p-2.5">
                        <div className="text-[12px] font-medium text-slate-800">{step.title}</div>
                        <div className="mt-0.5 text-[11px] leading-4 text-slate-500">{step.description}</div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {Object.entries(step.observed).map(([key, value]) => (
                            <span key={key} className="rounded bg-slate-50 px-1.5 py-0.5 font-mono text-[10.5px] text-slate-600">
                              {key}={compact(value)}
                            </span>
                          ))}
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
            )}
          </Card>
        </div>

        <aside className="space-y-4">
          <Card className="p-4">
            <SectionHeader title="Supplied deliveries" />
            <ul className="mt-2 space-y-2">
              {imports?.datasets.map((dataset) => (
                <li key={dataset.dataset} className="flex items-center justify-between gap-2 rounded-md border border-slate-200 px-2.5 py-2">
                  <div>
                    <div className="font-mono text-[11.5px] text-slate-700">{dataset.filename}</div>
                    <div className="text-[10.5px] text-slate-400">
                      {dataset.exists ? `${(dataset.bytes / 1024).toFixed(1)} KB` : "not found"}
                    </div>
                  </div>
                  <Badge tone={dataset.exists ? "success" : "danger"}>{dataset.exists ? "present" : "missing"}</Badge>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[10.5px] leading-4 text-slate-400">
              Files are served only through the import service; the raw deliveries are not exposed as static files.
            </p>
          </Card>

          <Card className="p-4">
            <SectionHeader title="Current state" />
            <dl className="mt-2 space-y-1.5 text-[12px]">
              <Row label="Records" value={String(imports?.current.records ?? 0)} />
              <Row label="Revision 1" value={String(revisions["1"] ?? 0)} />
              <Row label="Revision 2" value={String(revisions["2"] ?? 0)} />
              <Row
                label="Usable text"
                value={metrics ? `${metrics.totals.usable_text}/${metrics.totals.coverage_denominator}` : "—"}
              />
              <Row label="Coverage" value={metrics ? pct(metrics.totals.coverage_pct) : "—"} />
              <Row label="Needs review" value={String(metrics?.totals.needs_review ?? 0)} />
              <Row label="Manual overrides" value={String(metrics?.totals.manual_overrides ?? 0)} />
            </dl>
          </Card>

          <Card className={cx("p-4", m07?.manual_override && "border-indigo-200 bg-indigo-50/20")}>
            <SectionHeader title="M07 check" description="The record used to prove update and override behaviour." />
            {m07 ? (
              <dl className="mt-2 space-y-1.5 text-[12px]">
                <Row label="Applied revision" value={String(m07.applied_revision)} />
                <Row label="Usable text" value={m07.has_usable_text ? "yes" : "no"} />
                <Row label="Suggested" value={m07.suggested_route_labels.join(", ")} />
                <Row label="Effective" value={m07.effective_route_labels.join(", ")} />
                <Row label="Manual override" value={m07.manual_override ? "yes" : "no"} />
                <Row label="Review state" value={m07.review_label} />
                <Row label="Analysis" value={m07.analysis_freshness_label} />
              </dl>
            ) : (
              <p className="mt-2 text-[12px] text-slate-500">M07 is not imported yet.</p>
            )}
          </Card>

          <Card className="p-4">
            <SectionHeader title="What each rule does" />
            <ul className="mt-2 space-y-1.5 text-[11.5px] leading-5 text-slate-600">
              <li><strong className="font-medium text-slate-800">Identity:</strong> (source_type, source_id), never name, title, ref or position.</li>
              <li><strong className="font-medium text-slate-800">Newer wins:</strong> revision 2 replaces the whole payload, including nulls.</li>
              <li><strong className="font-medium text-slate-800">Older is ignored:</strong> a replay of revision 1 cannot overwrite revision 2.</li>
              <li><strong className="font-medium text-slate-800">Corrections survive:</strong> manual routes are a separate table and are only cleared by an explicit reset.</li>
              <li><strong className="font-medium text-slate-800">New text is flagged:</strong> analysis is refreshed or visibly marked pending review.</li>
            </ul>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function StepButton({
  index,
  title,
  description,
  onClick,
  busy,
  icon,
}: {
  index: string;
  title: string;
  description: string;
  onClick: () => void;
  busy: boolean;
  icon: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className="flex items-start gap-2.5 rounded-md border border-slate-200 px-2.5 py-2 text-left transition-colors hover:border-indigo-200 hover:bg-indigo-50/30 disabled:opacity-60"
    >
      <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded bg-slate-900 text-[10.5px] font-semibold text-white">
        {index}
      </span>
      <span className="min-w-0">
        <span className="flex items-center gap-1.5 text-[12.5px] font-medium text-slate-800">
          {icon} {busy ? "Working…" : title}
        </span>
        <span className="mt-0.5 block text-[11px] leading-4 text-slate-500">{description}</span>
      </span>
    </button>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  );
}

function compact(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") {
    const text = JSON.stringify(value);
    return text.length > 70 ? `${text.slice(0, 70)}…` : text;
  }
  const text = String(value);
  return text.length > 70 ? `${text.slice(0, 70)}…` : text;
}
