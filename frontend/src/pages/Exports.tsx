import { Archive, Download, FileJson, FileSpreadsheet, FolderTree, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorState, Loading, PageHeader, SectionHeader } from "../components/ui";
import { api } from "../lib/api";
import { cx, fmtDateTime, pct } from "../lib/format";
import type { ExportManifest } from "../lib/types";

type ExportState = {
  history: { version: number; created_at: string; record_count: number; superseded: boolean; state_hash: string }[];
  current: ExportManifest | null;
  version: number | null;
  created_at: string | null;
  download: { archive: string; manifest_json: string; manifest_csv: string } | null;
};

export function Exports() {
  const [data, setData] = useState<ExportState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .exports()
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const generate = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const result = await api.createExport();
      setNotice(result.message);
      load();
    } catch (err) {
      setNotice((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const tree = useMemo(() => {
    if (!data?.current) return [];
    const files = data.current.files ?? [];
    const grouped = new Map<string, string[]>();
    files.forEach((file) => {
      const parts = file.split("/");
      const dir = parts.slice(0, -1).join("/") || ".";
      grouped.set(dir, [...(grouped.get(dir) ?? []), parts[parts.length - 1]]);
    });
    return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [data]);

  if (loading && !data) return <Loading label="Loading export state" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const manifest = data?.current ?? null;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Exports"
        title="Organised outputs another person can find"
        description="Every export is a real set of files plus a JSON and CSV manifest. Paths are relative inside the archive; a repeated export of unchanged state reuses the current version."
        actions={
          <>
            <Button onClick={load} disabled={loading}>
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
            <Button variant="primary" onClick={generate} disabled={busy}>
              <Archive className="h-3.5 w-3.5" /> {busy ? "Generating…" : manifest ? "Generate new export" : "Generate export"}
            </Button>
          </>
        }
      />

      {notice ? (
        <div className="rounded-md border border-indigo-200 bg-indigo-50 px-3 py-2 text-[12.5px] text-indigo-800">
          {notice}
        </div>
      ) : null}

      {!manifest ? (
        <Card>
          <EmptyState
            icon={<Archive className="h-8 w-8" />}
            title="No export generated yet"
            body="Import at least one delivery, then generate the export archive. The manifest will list only files that actually exist inside the zip."
            action={
              <Button variant="primary" onClick={generate} disabled={busy}>
                Generate export
              </Button>
            }
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Card className="px-4 py-3">
              <div className="label-xs">Current version</div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-[24px] font-semibold text-slate-900">v{manifest.export_version}</span>
                <Badge tone="success">current</Badge>
              </div>
              <p className="mt-1 text-[11px] text-slate-500">{fmtDateTime(manifest.generated_at)}</p>
            </Card>
            <Card className="px-4 py-3">
              <div className="label-xs">Records in manifest</div>
              <div className="mt-1 text-[24px] font-semibold text-slate-900">{manifest.records.length}</div>
              <p className="mt-1 text-[11px] text-slate-500">
                {manifest.summary.calls} calls · {manifest.summary.meetings} meetings
              </p>
            </Card>
            <Card className="px-4 py-3">
              <div className="label-xs">Coverage in export</div>
              <div className="mt-1 text-[24px] font-semibold text-slate-900">
                {manifest.summary.usable_text}/{manifest.summary.coverage_denominator}
              </div>
              <p className="mt-1 text-[11px] text-slate-500">{pct(manifest.summary.coverage_pct)} of records</p>
            </Card>
            <Card className="px-4 py-3">
              <div className="label-xs">Manual overrides</div>
              <div className="mt-1 text-[24px] font-semibold text-slate-900">{manifest.summary.manual_overrides}</div>
              <p className="mt-1 text-[11px] text-slate-500">reflected as effective routes</p>
            </Card>
          </div>

          <Card className="p-4">
            <SectionHeader
              icon={<Download className="h-4 w-4" />}
              title="Download"
              description="The archive contains the manager brief, the overview, one output per effective route, needs-review intake files and both manifests."
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <a
                href={api.exportDownloadUrl("archive")}
                className="inline-flex items-center gap-1.5 rounded-md bg-indigo-700 px-3 py-1.5 text-[13px] font-medium text-white hover:bg-indigo-800"
              >
                <Archive className="h-4 w-4" /> revenue-intelligence-export.zip
              </a>
              <a
                href={api.exportDownloadUrl("manifest_json")}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-700 hover:bg-slate-50"
              >
                <FileJson className="h-4 w-4" /> manifest.json
              </a>
              <a
                href={api.exportDownloadUrl("manifest_csv")}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-700 hover:bg-slate-50"
              >
                <FileSpreadsheet className="h-4 w-4" /> manifest.csv
              </a>
            </div>
            <p className="mt-2 text-[11.5px] leading-5 text-slate-500">
              Versioning policy: the export is a state snapshot. If the application state is unchanged, the same
              version is returned and no duplicate outputs are written. A changed state creates v
              {manifest.export_version + 1} and marks this run superseded in history.
            </p>
          </Card>

          <div className="grid gap-4 xl:grid-cols-[330px_minmax(0,1fr)]">
            <Card className="p-4">
              <SectionHeader icon={<FolderTree className="h-4 w-4" />} title="Archive structure" />
              <div className="mt-3 space-y-2">
                {tree.map(([dir, files]) => (
                  <div key={dir}>
                    <div className="font-mono text-[11px] text-slate-500">{dir}/</div>
                    <ul className="mt-0.5 space-y-0.5 border-l border-slate-200 pl-2.5">
                      {files.map((file) => (
                        <li key={file} className="font-mono text-[11px] text-slate-700">{file}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="overflow-hidden">
              <div className="border-b border-slate-200 px-4 py-2.5">
                <h2 className="text-[14px] font-semibold text-slate-900">Manifest</h2>
                <p className="mt-0.5 text-[11.5px] text-slate-500">
                  JSON and CSV carry the same fields; both list only active output paths.
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="table-compact w-full min-w-[820px]">
                  <thead className="bg-slate-50/80">
                    <tr className="border-b border-slate-200 text-left">
                      <th className="px-3 py-2">Record</th>
                      <th className="px-3 py-2">Rev</th>
                      <th className="px-3 py-2">Effective route(s)</th>
                      <th className="px-3 py-2">Review</th>
                      <th className="px-3 py-2">Override</th>
                      <th className="px-3 py-2">Freshness</th>
                      <th className="px-3 py-2">Output path(s)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {manifest.records.map((record) => (
                      <tr key={`${record.source_type}-${record.source_id}`} className="hover:bg-slate-50/60">
                        <td className="px-3 py-2 font-medium text-slate-800">{record.record_ref}</td>
                        <td className="px-3 py-2 tabular-nums">{record.applied_revision}</td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-1">
                            {record.effective_routes.map((route) => (
                              <Badge key={route} tone="neutral">{route.replace(/_/g, " ")}</Badge>
                            ))}
                          </div>
                        </td>
                        <td className="px-3 py-2">{record.review_state.replace(/_/g, " ")}</td>
                        <td className="px-3 py-2">
                          {record.manual_override ? <Badge tone="accent">yes</Badge> : <span className="text-slate-400">no</span>}
                        </td>
                        <td className="px-3 py-2">{record.analysis_freshness.replace(/_/g, " ")}</td>
                        <td className="px-3 py-2">
                          <ul className="space-y-0.5">
                            {record.output_paths.map((path) => (
                              <li key={path} className="font-mono text-[10.5px] leading-4 text-slate-600">{path}</li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>

          <Card className="p-4">
            <SectionHeader title="Export history" description="Older versions remain listed and are marked superseded." />
            <table className="table-compact mt-3 w-full">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="py-1.5 pr-3">Version</th>
                  <th className="py-1.5 pr-3">Created</th>
                  <th className="py-1.5 pr-3">Records</th>
                  <th className="py-1.5 pr-3">State hash</th>
                  <th className="py-1.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data?.history.map((run) => (
                  <tr key={run.version}>
                    <td className="py-1.5 pr-3 font-medium">v{run.version}</td>
                    <td className="py-1.5 pr-3">{fmtDateTime(run.created_at)}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{run.record_count}</td>
                    <td className="py-1.5 pr-3 font-mono text-[10.5px] text-slate-500">{run.state_hash.slice(0, 12)}…</td>
                    <td className={cx("py-1.5", run.superseded ? "text-slate-400" : "text-emerald-700")}>
                      {run.superseded ? "superseded" : "current"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
