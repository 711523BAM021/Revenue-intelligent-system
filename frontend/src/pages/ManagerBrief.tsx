import { ArrowUpRight, CheckCircle2, ClipboardList, Info, Quote, TriangleAlert, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, ErrorState, Loading, Metric, PageHeader, SectionHeader } from "../components/ui";
import { api } from "../lib/api";
import { cx, pct, reviewTone } from "../lib/format";
import type { BriefData } from "../lib/types";

export function ManagerBrief() {
  const [data, setData] = useState<BriefData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .brief()
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading label="Loading the manager brief" />;
  if (error) return <ErrorState message={error} />;
  if (!data) return null;

  const { brief, metrics } = data;
  const t = metrics.totals;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Manager Brief"
        title={brief.title}
        description={brief.standfirst}
        actions={
          <>
            <Badge tone="neutral">Fixed to 21 Aug 2026</Badge>
            <Link
              to="/exports"
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-700 hover:bg-slate-50"
            >
              Export brief <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </>
        }
      />

      {t.records === 0 ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-[12.5px] text-amber-900">
          No deliveries are imported, so the activity strip reads zero. The narrative below is pre-generated from the
          supplied conversations; load the demo state in the <Link to="/imports" className="underline">Import lab</Link>{" "}
          to connect it to live records.
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Selected records" value={t.records} sub={`${t.calls} calls · ${t.meetings} meetings`} tone="accent" />
        <Metric label="Usable supplied text" value={`${t.usable_text}/${t.coverage_denominator}`} sub={pct(t.coverage_pct)} tone="info" />
        <Metric label="Needs review" value={t.needs_review} sub={`${t.awaiting_text} awaiting text`} tone="warning" />
        <Metric label="Manual overrides" value={t.manual_overrides} sub={`${t.route_assignments} route assignments`} tone="success" />
      </div>

      <div className="rounded-md border border-slate-200 bg-white px-3.5 py-2.5 text-[11.5px] leading-5 text-slate-600">
        <Info className="mr-1 inline h-3.5 w-3.5 text-slate-400" />
        {brief.scope_note} Activity numbers and the “verified” marks on evidence are calculated at runtime; the
        narrative is pre-generated and does not change with dashboard filters.
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_330px]">
        <div className="space-y-4">
          {brief.sections.map((section) => (
            <Card key={section.id} className="p-4">
              <SectionHeader
                icon={<ClipboardList className="h-4 w-4" />}
                title={section.title}
                description={section.intro}
              />
              <ul className="mt-3 divide-y divide-slate-100">
                {section.items.map((item) => (
                  <li key={`${section.id}-${item.record_ref}`} className="py-2.5 first:pt-1 last:pb-0">
                    <div className="flex items-start gap-2.5">
                      <Link
                        to={item.record ? `/conversations/${item.record.source_type}/${item.record.source_id}` : "/conversations"}
                        className="mt-0.5 inline-flex h-5 shrink-0 items-center rounded px-1.5 text-[10.5px] font-semibold uppercase text-indigo-700 hover:bg-indigo-50"
                        title={`Open ${item.record_ref}`}
                      >
                        {item.record_ref}
                      </Link>
                      <div className="min-w-0">
                        <p className="text-[13px] leading-5 text-slate-800">{item.text}</p>
                        {item.evidence.map((evidence, index) => (
                          <div key={index} className="mt-1.5 flex items-start gap-1.5">
                            <Quote className="mt-0.5 h-3 w-3 shrink-0 text-slate-300" />
                            <p className="text-[11.5px] leading-5 text-slate-600">
                              “{evidence.quote}”
                              <span className="text-slate-400">
                                {" "}
                                — {evidence.kind === "turn" ? `turn ${evidence.turn}` : "call transcript"}
                              </span>
                              {evidence.verified === true ? (
                                <span className="ml-1.5 inline-flex items-center gap-0.5 text-emerald-700">
                                  <CheckCircle2 className="h-3 w-3" /> verified in source
                                </span>
                              ) : evidence.verified === false ? (
                                <span className="ml-1.5 inline-flex items-center gap-0.5 text-rose-700">
                                  <TriangleAlert className="h-3 w-3" /> not found in current text
                                </span>
                              ) : null}
                            </p>
                          </div>
                        ))}
                        {item.record ? (
                          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                            <Badge tone={reviewTone(item.record.review_state)}>{item.record.review_label}</Badge>
                            {item.record.manual_override ? <Badge tone="accent">Manual override</Badge> : null}
                            <span className="text-[11px] text-slate-400">
                              {item.record.effective_route_labels.join(" · ")}
                            </span>
                          </div>
                        ) : (
                          <p className="mt-1 text-[11px] text-rose-700">Record not present in the current import.</p>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          ))}

          <Card className="p-4">
            <SectionHeader
              icon={<XCircle className="h-4 w-4" />}
              title="Decision deliberately rejected"
              description={data.rejected_decision.title}
            />
            <dl className="mt-3 space-y-2.5 text-[12.5px] leading-5">
              <div>
                <dt className="label-xs">Alternative considered</dt>
                <dd className="mt-0.5 text-slate-700">{data.rejected_decision.alternative}</dd>
              </div>
              <div>
                <dt className="label-xs">Why it was rejected</dt>
                <dd className="mt-0.5 text-slate-700">{data.rejected_decision.why_rejected}</dd>
              </div>
              <div>
                <dt className="label-xs">Trade-off accepted</dt>
                <dd className="mt-0.5 text-slate-700">{data.rejected_decision.trade_off}</dd>
              </div>
              <div>
                <dt className="label-xs">Where the final choice appears</dt>
                <dd className="mt-0.5 text-slate-700">{data.rejected_decision.where_it_appears}</dd>
              </div>
            </dl>
            <p className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-[11.5px] text-slate-600">
              {data.rejected_decision.screen}
            </p>
          </Card>
        </div>

        <aside className="space-y-4">
          <Card className="p-4">
            <SectionHeader title="Three strongest findings" description="Each is checked against the supplied text." />
            <ol className="mt-3 space-y-3">
              {data.findings.map((finding, index) => (
                <li key={finding.id} className="rounded-md border border-slate-200 p-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-[12.5px] font-semibold leading-5 text-slate-800">
                      {index + 1}. {finding.title}
                    </h3>
                    {finding.verified ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                    ) : (
                      <TriangleAlert className="h-3.5 w-3.5 shrink-0 text-rose-600" />
                    )}
                  </div>
                  <p className="mt-1 text-[11.5px] leading-5 text-slate-600">{finding.observation}</p>
                  <p className="mt-1 text-[11.5px] leading-5 text-slate-500">
                    <span className="font-medium text-slate-700">Why it matters: </span>
                    {finding.why_it_matters}
                  </p>
                  <p className="mt-1.5 border-l-2 border-amber-200 pl-2 text-[11.5px] leading-5 text-slate-700">
                    “{finding.evidence.quote}”
                    <span className="block text-[10.5px] text-slate-400">
                      {finding.evidence.record_ref} ·{" "}
                      {finding.evidence.kind === "turn" ? `turn ${finding.evidence.turn}` : "call transcript"}
                    </span>
                  </p>
                  <p className="mt-1 text-[10.5px] leading-4 text-slate-500">
                    Affects: {finding.affected_surface}
                  </p>
                </li>
              ))}
            </ol>
          </Card>

          <Card className="p-4">
            <SectionHeader icon={<TriangleAlert className="h-4 w-4" />} title={brief.uncertainty.title} />
            <ul className="mt-2 space-y-2 text-[11.5px] leading-5 text-slate-600">
              {brief.uncertainty.items.map((item) => (
                <li key={item} className="flex items-start gap-1.5">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
                  {item}
                </li>
              ))}
            </ul>
          </Card>

          <Card className="p-4">
            <SectionHeader title="Metric definitions" />
            <dl className="mt-2 space-y-2">
              {data.metrics_notes.map((note) => (
                <div key={note.metric}>
                  <dt className="text-[11.5px] font-semibold text-slate-700">{note.metric}</dt>
                  <dd className="text-[11px] leading-4 text-slate-600">{note.definition}</dd>
                </div>
              ))}
            </dl>
            <p className={cx("mt-2 text-[10.5px] leading-4 text-slate-400")}>{data.generated_from}</p>
          </Card>
        </aside>
      </div>
    </div>
  );
}
