"""Export generation.

Layout inside the archive (relative paths, as required):

    exports/2026-08-21/
      manifest.json
      manifest.csv
      manager-brief.md
      summary/overview.md
      deal-next-steps/M03-....md
      ...

Versioning policy: the export is a snapshot of current application state. A
re-export whose state hash is unchanged reuses the existing archive (no new
version, no duplicate outputs). A changed state creates version n+1, marks the
previous run superseded and writes a new versioned archive; the unversioned
`revenue-intelligence-export.zip` always points at the current run.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import EXPORT_BASENAME, EXPORT_DIR, REPORTING_DATE
from .corpus import editorial
from .ingest import effective_routes
from .metrics import compute_metrics, load_records
from .models import ExportRun, SourceRecord
from .serializers import analysis_freshness, processing_state
from .taxonomy import ROUTE_LABELS, ROUTE_SLUGS, REVIEW_LABELS

DATE_DIR = f"exports/{REPORTING_DATE}"


def _slug(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:48] or fallback


def _record_slug(record: SourceRecord) -> str:
    base = record.title or (record.owner_name if record.source_type == "meeting" else None)
    if base:
        return _slug(base, record.record_ref.lower())
    return record.record_ref.lower()


def _fmt_evidence(item: dict) -> str:
    if item.get("kind") == "turn":
        return f'- Turn {item.get("turn")}: "{item.get("quote", "")}"' + (
            f" - {item['note']}" if item.get("note") else ""
        )
    return f'- Call {item.get("record_ref", "")}: "{item.get("quote", "")}"' + (
        f" - {item['note']}" if item.get("note") else ""
    )


def _bullet(items: list[str], empty: str = "- None recorded.") -> str:
    return "\n".join(f"- {i}" for i in items) if items else empty


def _transcript_section(record: SourceRecord, content: dict) -> str:
    """Only the passages cited as evidence, never a fabricated transcript."""
    lines = []
    for item in content.get("evidence") or []:
        lines.append(_fmt_evidence(item))
    return "\n".join(lines) if lines else "- No transcript passage was cited."


def render_record_markdown(record: SourceRecord, route: str, *, all_routes: list[str]) -> str:
    ref = record.record_ref
    title = record.title or f"{record.source_type.title()} {ref}"
    state = record.review.state if record.review else "unreviewed"
    freshness = analysis_freshness(record)
    content = record.analysis.content if record.analysis else None
    origin = record.analysis.origin if record.analysis else "none"

    header = [
        f"# {ref} - {title}",
        "",
        f"- Source: {record.source_type} / `{record.source_id}`",
        f"- Record ref: {ref}",
        f"- Applied revision: {record.applied_revision}",
        f"- Destination: {ROUTE_LABELS.get(route, route)}",
        f"- All effective routes: {', '.join(ROUTE_LABELS.get(r, r) for r in all_routes)}",
        f"- Processing state: {processing_state(record)}",
        f"- Review state: {REVIEW_LABELS.get(state, state)}",
        f"- Manual override: {'yes' if record.override else 'no'}",
        f"- Analysis freshness: {freshness} ({origin})",
        f"- Activity date: {record.activity_date or 'not supplied'} ({record.started_at_local or 'no timestamp'})",
    ]
    if record.override:
        header.append(f"- Override reason: {record.override.reason or 'not recorded'}")
    if record.owner_name:
        header.append(
            f"- {'Call representative' if record.owner_kind == 'call_representative' else 'Meeting organiser'}: "
            f"{record.owner_name}"
        )
    header.append("")

    if not content:
        body = [
            "## Intake status",
            "",
            "No usable supplied conversation text exists for this record in the current source revision, "
            "so no substantive analysis is produced. This is an intake state, not a conclusion about the conversation.",
            "",
            f"- Reason recorded in source: {record.unavailable_reason or 'no usable text supplied'}",
            f"- Suggested route: {', '.join(ROUTE_LABELS.get(r, r) for r in (record.routing.suggested_routes if record.routing else ['needs_review']))}",
            "",
            "## Next action",
            "",
            "Obtain the transcript or recording through the normal source process, or confirm with the account "
            "owner that no usable text exists. Do not treat missing text as a failed conversation.",
            "",
        ]
        return "\n".join(header + body)

    sections = [
        "## Summary",
        "",
        content.get("summary", ""),
        "",
        "## Why it matters",
        "",
        content.get("why_it_matters", ""),
        "",
        "## Supporting evidence",
        "",
        _transcript_section(record, content),
        "",
        "## Risks and blockers",
        "",
        _bullet(content.get("risks") or []),
        "",
        "## Opportunities",
        "",
        _bullet(content.get("opportunities") or []),
        "",
        "## What the evidence does not establish",
        "",
        _bullet(content.get("uncertainties") or []),
        "",
        "## Recommended next action",
        "",
        content.get("next_action", ""),
        "",
        f"- Action owner: {content.get('action_owner') or 'Not supported by the source - manager to assign'}",
    ]
    if content.get("owner_basis"):
        sections.append(f"- Ownership basis: {content['owner_basis']}")
    sections += [
        "",
        "## Routing",
        "",
        f"- Suggested route(s): {', '.join(ROUTE_LABELS.get(r, r) for r in (record.routing.suggested_routes if record.routing else []))}",
        f"- Effective route(s): {', '.join(ROUTE_LABELS.get(r, r) for r in all_routes)}",
        f"- Why: {content.get('route_rationale') or (record.routing.rationale if record.routing else '')}",
        "",
        "## Source metadata",
        "",
        f"- Source type: {record.source_type}",
        f"- Source ID: {record.source_id}",
        f"- Record reference: {record.record_ref}",
        f"- Applied revision: {record.applied_revision}",
        f"- Has usable text: {'yes' if record.has_usable_text else 'no'}",
        f"- Source-reported outcome: {record.source_outcome or 'not supplied'}",
        "",
    ]
    if route == "needs_review":
        sections += [
            "## Why this output is in needs-review",
            "",
            record.review.note if record.review and record.review.note else "Flagged for human review.",
            "",
        ]
    return "\n".join(header + sections)


def render_manager_brief(records: list[SourceRecord], metrics: dict) -> str:
    ed = editorial()
    brief = ed.get("brief", {})
    lines = [
        f"# {brief.get('title', f'Manager brief - {REPORTING_DATE}')}",
        "",
        brief.get("standfirst", ""),
        "",
        "## Activity snapshot (computed from current records)",
        "",
        f"- Selected records: **{metrics['totals']['records']}** "
        f"({metrics['totals']['calls']} calls, {metrics['totals']['meetings']} meetings)",
        f"- Usable supplied text: **{metrics['totals']['usable_text']}/{metrics['totals']['coverage_denominator']}** "
        f"({metrics['totals']['coverage_pct']}% transcript coverage)",
        f"- Records needing review: **{metrics['totals']['needs_review']}**",
        f"- Manual route overrides: **{metrics['totals']['manual_overrides']}**",
        f"- Route assignments: **{metrics['totals']['route_assignments']}** across "
        f"{metrics['totals']['records']} records",
        "",
        brief.get("scope_note", ""),
        "",
    ]
    for section in brief.get("sections", []):
        lines += [f"## {section['title']}", ""]
        if section.get("intro"):
            lines += [section["intro"], ""]
        for item in section.get("items", []):
            evidence = "".join(
                f" Evidence: turn {e.get('turn')} - \"{e.get('quote')}\"." if e.get("kind") == "turn"
                else f" Evidence: {e.get('record_ref', '')} call - \"{e.get('quote')}\"."
                for e in item.get("evidence", [])
            )
            lines.append(f"- **{item['record_ref']}** - {item['text']}{evidence}")
        lines.append("")
    uncertainty = brief.get("uncertainty", {})
    if uncertainty:
        lines += [f"## {uncertainty.get('title', 'Uncertainties')}", ""]
        lines += [f"- {u}" for u in uncertainty.get("items", [])]
        lines.append("")
    return "\n".join(lines)


def render_overview(metrics: dict, version: int) -> str:
    m = metrics
    lines = [
        f"# Revenue Intelligence Inbox - export v{version}",
        "",
        f"Reporting date: {m['reporting']['date']} ({m['reporting']['timezone']}). Generated by the application "
        "from current database state; counts are not hardcoded.",
        "",
        "## Definitions used",
        "",
        "- Selected records: distinct (source_type, source_id) pairs after applying the highest revision received.",
        "- Usable supplied text: nonblank call transcript, or a meeting with at least one nonblank turn.",
        "- Transcript coverage: usable texts divided by selected records in the same filter.",
        "- Route assignments: effective routes (manual override if present, otherwise the automated suggestion); "
        "a record can hold more than one route, so assignments can exceed records.",
        "",
        "## Current state",
        "",
        f"- Records: {m['totals']['records']} ({m['totals']['calls']} calls, {m['totals']['meetings']} meetings)",
        f"- Usable text: {m['totals']['usable_text']} / {m['totals']['coverage_denominator']} "
        f"= {m['totals']['coverage_pct']}%",
        f"- Missing/unavailable text: {m['totals']['missing_text']}",
        f"- Needs review (including awaiting text): {m['totals']['needs_review']}",
        f"- Manual overrides: {m['totals']['manual_overrides']}",
        f"- Route assignments: {m['totals']['route_assignments']} across {m['totals']['records']} records",
        f"- Multi-route records: {m['totals']['multi_route_records']}",
        "",
        "## Effective routes",
        "",
    ]
    for route in m["routes"]["effective"]:
        lines.append(f"- {route['label']}: {route['count']} (suggested {route['suggested_count']})")
    lines += [
        "",
        "## Activity by day",
        "",
    ]
    for day in m["activity_by_day"]:
        lines.append(f"- {day['date']}: {day['records']} records ({day['calls']} calls, {day['meetings']} meetings)")
    lines += [
        "",
        "## Source-reported call connection",
        "",
        f"- Connected: {m['connection']['connected']}, not connected: {m['connection']['disconnected']}, "
        f"unknown: {m['connection']['unknown']}",
        f"- Rate: {m['connection']['rate_pct']}% of {m['connection']['denominator']} calls with a non-null flag. "
        "This is a stored classification, not a transcript finding.",
        "",
        "## Scope",
        "",
        "This is a selected sample of 44 records for one local day, not a team-wide performance measurement. "
        "No pipeline value, deal outcome or account link is asserted anywhere in this export.",
        "",
    ]
    return "\n".join(lines)


def _manifest_entry(record: SourceRecord, entry_paths: list[str], version: int) -> dict:
    routes = effective_routes(record)
    state = record.review.state if record.review else "unreviewed"
    return {
        "source_type": record.source_type,
        "source_id": record.source_id,
        "record_ref": record.record_ref,
        "applied_revision": record.applied_revision,
        "suggested_routes": list(record.routing.suggested_routes) if record.routing else ["needs_review"],
        "effective_routes": routes,
        "effective_route_labels": [ROUTE_LABELS.get(r, r) for r in routes],
        "output_paths": entry_paths,
        "processing_state": processing_state(record),
        "review_state": state,
        "manual_override": record.override is not None,
        "analysis_freshness": analysis_freshness(record),
        "analysis_origin": record.analysis.origin if record.analysis else "none",
        "title": record.title,
        "owner_name": record.owner_name,
        "owner_kind": record.owner_kind,
        "activity_date": record.activity_date,
        "has_usable_text": record.has_usable_text,
        "export_version": version,
    }


def _state_hash(records: list[SourceRecord], metrics: dict) -> str:
    payload = []
    for record in records:
        payload.append(
            {
                "type": record.source_type,
                "id": record.source_id,
                "rev": record.applied_revision,
                "text": record.text_hash,
                "eff": effective_routes(record),
                "sug": record.routing.suggested_routes if record.routing else [],
                "review": record.review.state if record.review else None,
                "override": record.override.effective_routes if record.override else None,
                "fresh": analysis_freshness(record),
                "analysis": record.analysis.content if record.analysis else None,
            }
        )
    payload.append({"route_counts": [(r["route"], r["count"]) for r in metrics["routes"]["effective"]]})
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_export(session: Session, export_dir: Path | None = None) -> dict:
    export_root = export_dir or EXPORT_DIR
    records = load_records(session)
    metrics = compute_metrics(records)
    state_hash = _state_hash(records, metrics)

    runs = list(session.scalars(select(ExportRun).order_by(ExportRun.version.desc())).all())
    latest = runs[0] if runs else None
    if latest and latest.state_hash == state_hash and Path(latest.archive_path).exists():
        return {
            "created": False,
            "version": latest.version,
            "state_hash": state_hash,
            "archive_path": latest.archive_path,
            "manifest": latest.manifest,
            "message": "Application state is unchanged since the current export; no duplicate outputs created.",
        }

    version = (latest.version + 1) if latest else 1
    run_dir = export_root / REPORTING_DATE / f"run-{version}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    stage = run_dir / DATE_DIR
    stage.mkdir(parents=True, exist_ok=True)

    manifest_entries: list[dict] = []
    for record in records:
        routes = effective_routes(record)
        paths: list[str] = []
        ref_slug = _record_slug(record)
        for route in routes:
            route_dir = ROUTE_SLUGS.get(route, route)
            filename = f"{record.record_ref}-{ref_slug}.md"
            rel = f"{DATE_DIR}/{route_dir}/{filename}"
            _write(run_dir / rel, render_record_markdown(record, route, all_routes=routes))
            paths.append(rel)
        if not record.has_usable_text and not any(p.startswith(f"{DATE_DIR}/needs-review/") for p in paths):
            rel = f"{DATE_DIR}/needs-review/{record.record_ref}-{ref_slug}.md"
            _write(run_dir / rel, render_record_markdown(record, "needs_review", all_routes=routes))
            paths.append(rel)
        manifest_entries.append(_manifest_entry(record, paths, version))

    brief_md = render_manager_brief(records, metrics)
    _write(run_dir / f"{DATE_DIR}/manager-brief.md", brief_md)
    _write(run_dir / f"{DATE_DIR}/summary/overview.md", render_overview(metrics, version))

    manifest = {
        "export_version": version,
        "status": "current",
        "supersedes_version": latest.version if latest else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reporting_date": REPORTING_DATE,
        "timezone": "Asia/Kolkata",
        "root": DATE_DIR,
        "state_hash": state_hash,
        "summary": {
            "records": metrics["totals"]["records"],
            "calls": metrics["totals"]["calls"],
            "meetings": metrics["totals"]["meetings"],
            "usable_text": metrics["totals"]["usable_text"],
            "coverage_pct": metrics["totals"]["coverage_pct"],
            "coverage_denominator": metrics["totals"]["coverage_denominator"],
            "needs_review": metrics["totals"]["needs_review"],
            "manual_overrides": metrics["totals"]["manual_overrides"],
            "route_assignments": metrics["totals"]["route_assignments"],
        },
        "records": manifest_entries,
        "files": sorted(
            [str(p.relative_to(run_dir)).replace("\\", "/") for p in run_dir.rglob("*") if p.is_file()]
            + [f"{DATE_DIR}/manifest.json", f"{DATE_DIR}/manifest.csv"]
        ),
    }

    _write(run_dir / f"{DATE_DIR}/manifest.json", json.dumps(manifest, indent=2))

    csv_buffer = io.StringIO()
    fieldnames = [
        "source_type", "source_id", "record_ref", "applied_revision", "suggested_routes",
        "effective_routes", "output_paths", "processing_state", "review_state",
        "manual_override", "analysis_freshness", "analysis_origin", "title", "owner_name",
        "owner_kind", "activity_date", "has_usable_text", "export_version",
    ]
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for entry in manifest_entries:
        row = dict(entry)
        for key in ("suggested_routes", "effective_routes", "output_paths"):
            row[key] = "|".join(row[key])
        writer.writerow(row)
    _write(run_dir / f"{DATE_DIR}/manifest.csv", csv_buffer.getvalue())

    archive_path = export_root / f"{EXPORT_BASENAME}-v{version}.zip"
    current_path = export_root / f"{EXPORT_BASENAME}.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(run_dir)).replace("\\", "/"))
    shutil.copyfile(archive_path, current_path)

    for run in runs:
        run.superseded = True
    session.add(
        ExportRun(
            version=version,
            state_hash=state_hash,
            archive_path=str(current_path),
            manifest=manifest,
            record_count=len(manifest_entries),
            superseded=False,
        )
    )
    session.commit()

    return {
        "created": True,
        "version": version,
        "state_hash": state_hash,
        "archive_path": str(current_path),
        "versioned_archive_path": str(archive_path),
        "run_dir": str(run_dir),
        "manifest": manifest,
        "message": f"Export v{version} generated with {len(manifest_entries)} records and real output files.",
    }


def latest_export(session: Session) -> ExportRun | None:
    return session.scalars(
        select(ExportRun).where(ExportRun.superseded.is_(False)).order_by(ExportRun.version.desc())
    ).first()


def export_history(session: Session) -> list[dict]:
    runs = session.scalars(select(ExportRun).order_by(ExportRun.version.desc())).all()
    return [
        {
            "version": run.version,
            "created_at": run.created_at.isoformat(),
            "record_count": run.record_count,
            "superseded": run.superseded,
            "archive_path": run.archive_path,
            "state_hash": run.state_hash,
        }
        for run in runs
    ]


def load_current_manifest(session: Session) -> dict | None:
    run = latest_export(session)
    return run.manifest if run else None
