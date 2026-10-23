from __future__ import annotations

import json
import random
import tempfile
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import DATASET_FILES, DATA_DIR, REPORTING_DATE, REPORTING_TZ
from .corpus import all_analyses, editorial
from .db import get_db
from .exports import build_export, export_history, latest_export
from .ingest import (
    ImportValidationError,
    apply_delivery,
    effective_routes,
    parse_delivery,
    record_failed_import,
    reset_workspace,
)
from .metrics import apply_filters, compute_metrics, load_records
from .replay import run_replay
from .models import (
    Analysis,
    AnalysisHistory,
    AuditEvent,
    ExportRun,
    ImportBatch,
    ReviewState,
    RouteOverride,
    SourceRecord,
    utcnow,
)
from .serializers import record_to_dict
from .taxonomy import (
    REVIEW_LABELS,
    REVIEW_STATES,
    ROUTE_LABELS,
    ROUTE_ORDER,
    ROUTES,
    normalise_routes,
)

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class ImportRequest(BaseModel):
    dataset: str = Field(description="initial or update")
    shuffle: bool = False
    expected_revision: int | None = None


class OverrideRequest(BaseModel):
    routes: list[str]
    reason: str | None = None


class ReviewRequest(BaseModel):
    state: str
    note: str | None = None


class AnalysisRequest(BaseModel):
    summary: str
    why_it_matters: str = ""
    evidence: list[dict] = []
    risks: list[str] = []
    opportunities: list[str] = []
    uncertainties: list[str] = []
    next_action: str = ""
    action_owner: str | None = None
    owner_basis: str | None = None


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _get_record(session: Session, source_type: str, source_id: str) -> SourceRecord:
    record = session.scalar(
        select(SourceRecord)
        .where(SourceRecord.source_type == source_type, SourceRecord.source_id == source_id)
        .options(
            selectinload(SourceRecord.analysis),
            selectinload(SourceRecord.routing),
            selectinload(SourceRecord.review),
            selectinload(SourceRecord.override),
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


def _audit(session: Session, record_id: int, kind: str, detail: dict) -> None:
    session.add(AuditEvent(record_id=record_id, kind=kind, detail=detail))


def _dataset_info() -> list[dict]:
    out = []
    for key, filename in DATASET_FILES.items():
        path = DATA_DIR / filename
        out.append(
            {
                "dataset": key,
                "filename": filename,
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return out


def _read_dataset(dataset: str) -> tuple[Path, int]:
    if dataset not in DATASET_FILES:
        raise HTTPException(status_code=400, detail="dataset must be 'initial' or 'update'")
    path = DATA_DIR / DATASET_FILES[dataset]
    if not path.exists():
        raise HTTPException(
            status_code=409,
            detail=(
                f"Dataset file {path.name} was not found in the data directory. "
                "Place the supplied delivery files there (see README) and retry."
            ),
        )
    return path, (1 if dataset == "initial" else 2)


# --------------------------------------------------------------------------
# Meta / health
# --------------------------------------------------------------------------


@router.get("/health")
def health(session: Session = Depends(get_db)):
    return {"status": "ok", "records": session.query(SourceRecord).count()}


@router.get("/meta")
def meta(session: Session = Depends(get_db)):
    return {
        "reporting_date": REPORTING_DATE,
        "timezone": REPORTING_TZ,
        "routes": [
            {"key": key, **ROUTES[key], "order": index}
            for index, key in enumerate(ROUTE_ORDER)
        ],
        "review_states": [{"key": k, "label": REVIEW_LABELS[k]} for k in REVIEW_STATES],
        "datasets": _dataset_info(),
        "counts": {
            "records": session.query(SourceRecord).count(),
            "imports": session.query(ImportBatch).count(),
            "exports": session.query(ExportRun).count(),
        },
    }


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------


@router.get("/records")
def list_records(
    person: str | None = None,
    source_type: str | None = None,
    route: str | None = None,
    review_state: str | None = None,
    text: str | None = None,
    override: str | None = None,
    freshness: str | None = None,
    search: str | None = None,
    date: str | None = None,
    session: Session = Depends(get_db),
):
    all_records = load_records(session)
    records = apply_filters(
        all_records,
        person=person,
        source_type=source_type,
        route=route,
        review_state=review_state,
        text=text,
        override=override,
        freshness=freshness,
        search=search,
        date=date,
    )
    people = sorted({r.owner_name for r in all_records if r.owner_name})
    return {
        "total": len(records),
        "records": [record_to_dict(r) for r in records],
        "facets": {
            "people": people,
            "routes": [{"key": k, "label": ROUTE_LABELS[k]} for k in ROUTE_ORDER],
            "review_states": [{"key": k, "label": REVIEW_LABELS[k]} for k in REVIEW_STATES],
            "dates": sorted({r.activity_date for r in all_records if r.activity_date}),
        },
        "filters": {
            "person": person,
            "source_type": source_type,
            "route": route,
            "review_state": review_state,
            "text": text,
            "override": override,
            "freshness": freshness,
            "search": search,
            "date": date,
        },
    }


@router.get("/records/{source_type}/{source_id}")
def get_record(source_type: str, source_id: str, session: Session = Depends(get_db)):
    record = _get_record(session, source_type, source_id)
    data = record_to_dict(record, include_transcript=True)
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.record_id == record.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(20)
    ).all()
    data["history"] = [
        {"kind": e.kind, "detail": e.detail, "created_at": e.created_at.isoformat()}
        for e in events
    ]
    archived = session.scalars(
        select(AnalysisHistory)
        .where(AnalysisHistory.record_id == record.id)
        .order_by(AnalysisHistory.archived_at.desc())
        .limit(5)
    ).all()
    data["archived_analyses"] = [
        {
            "origin": a.origin,
            "freshness": a.freshness,
            "source_revision": a.source_revision,
            "archived_at": a.archived_at.isoformat(),
            "reason": a.archive_reason,
        }
        for a in archived
    ]
    data["import_events"] = [
        {
            "batch_id": b.batch_id,
            "filename": b.filename,
            "revision": b.delivery_revision,
            "status": b.status,
            "imported_at": b.imported_at.isoformat(),
            "inserted": b.inserted,
            "updated": b.updated,
            "ignored": b.ignored,
            "record_actions": [
                r for r in (b.details or {}).get("records", [])
                if r.get("record_ref") == record.record_ref
            ],
        }
        for b in session.scalars(select(ImportBatch).order_by(ImportBatch.imported_at.desc())).all()
    ]
    return data


# --------------------------------------------------------------------------
# Manual decisions
# --------------------------------------------------------------------------


@router.patch("/records/{source_type}/{source_id}/override")
def set_override(
    source_type: str,
    source_id: str,
    payload: OverrideRequest,
    session: Session = Depends(get_db),
):
    record = _get_record(session, source_type, source_id)
    routes = normalise_routes(payload.routes)
    if not routes:
        raise HTTPException(status_code=400, detail="At least one valid route is required")
    previous = record.override.effective_routes if record.override else None
    if record.override is None:
        record.override = RouteOverride(
            record_id=record.id,
            effective_routes=routes,
            reason=payload.reason,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    else:
        record.override.effective_routes = routes
        record.override.reason = payload.reason
        record.override.updated_at = utcnow()
    _audit(
        session,
        record.id,
        "route_override",
        {"from": previous, "to": routes, "reason": payload.reason},
    )
    session.commit()
    session.expire_all()
    return record_to_dict(_get_record(session, source_type, source_id))


@router.delete("/records/{source_type}/{source_id}/override")
def reset_override(source_type: str, source_id: str, session: Session = Depends(get_db)):
    record = _get_record(session, source_type, source_id)
    if record.override is None:
        raise HTTPException(status_code=400, detail="This record has no manual override to reset")
    previous = list(record.override.effective_routes)
    session.delete(record.override)
    session.flush()
    _audit(session, record.id, "route_override_reset", {"removed": previous})
    session.commit()
    session.expire_all()
    return record_to_dict(_get_record(session, source_type, source_id))


@router.patch("/records/{source_type}/{source_id}/review")
def set_review(
    source_type: str,
    source_id: str,
    payload: ReviewRequest,
    session: Session = Depends(get_db),
):
    record = _get_record(session, source_type, source_id)
    if payload.state not in REVIEW_STATES:
        raise HTTPException(status_code=400, detail=f"Unknown review state {payload.state!r}")
    if record.review is None:
        record.review = ReviewState(
            record_id=record.id,
            state=payload.state,
            note=payload.note,
            updated_at=utcnow(),
        )
    else:
        record.review.state = payload.state
        record.review.note = payload.note
        record.review.updated_at = utcnow()
    _audit(session, record.id, "review_state", {"state": payload.state, "note": payload.note})
    session.commit()
    return record_to_dict(_get_record(session, source_type, source_id))


@router.put("/records/{source_type}/{source_id}/analysis")
def save_analysis(
    source_type: str,
    source_id: str,
    payload: AnalysisRequest,
    session: Session = Depends(get_db),
):
    record = _get_record(session, source_type, source_id)
    if not record.has_usable_text:
        raise HTTPException(
            status_code=400,
            detail="No usable supplied text exists for this record; a substantive analysis cannot be authored.",
        )
    suggested = list(record.routing.suggested_routes) if record.routing else ["needs_review"]
    content = {
        "summary": payload.summary,
        "why_it_matters": payload.why_it_matters,
        "evidence": payload.evidence,
        "risks": payload.risks,
        "opportunities": payload.opportunities,
        "uncertainties": payload.uncertainties,
        "next_action": payload.next_action,
        "action_owner": payload.action_owner,
        "owner_basis": payload.owner_basis,
        "suggested_routes": suggested,
        "route_rationale": record.routing.rationale if record.routing else None,
        "route_trace": record.routing.trace if record.routing else [],
        "review_status": "reviewed",
        "analysis_basis": "Manager-authored in the application",
    }
    if record.analysis is not None:
        session.add(
            AnalysisHistory(
                record_id=record.id,
                content=record.analysis.content,
                origin=record.analysis.origin,
                freshness=record.analysis.freshness,
                source_revision=record.analysis.source_revision,
                text_hash=record.analysis.text_hash,
                archive_reason="Replaced by manager-authored analysis",
            )
        )
        record.analysis.content = content
        record.analysis.origin = "human_assisted"
        record.analysis.author = "manager"
        record.analysis.freshness = "current"
        record.analysis.source_revision = record.applied_revision
        record.analysis.text_hash = record.text_hash
        record.analysis.updated_at = utcnow()
    else:
        record.analysis = Analysis(
            record_id=record.id,
            content=content,
            origin="human_assisted",
            author="manager",
            freshness="current",
            source_revision=record.applied_revision,
            text_hash=record.text_hash,
            engine_version="human",
        )
    if record.review is None:
        record.review = ReviewState(
            record_id=record.id,
            state="reviewed",
            note="Manager-authored analysis saved.",
            updated_at=utcnow(),
        )
    else:
        record.review.state = "reviewed"
        record.review.note = "Manager-authored analysis saved."
        record.review.updated_at = utcnow()
    _audit(session, record.id, "analysis_human_assisted", {"summary": payload.summary[:200]})
    session.commit()
    return record_to_dict(_get_record(session, source_type, source_id), include_transcript=True)


@router.post("/records/{source_type}/{source_id}/analysis/pending")
def mark_analysis_pending(source_type: str, source_id: str, session: Session = Depends(get_db)):
    record = _get_record(session, source_type, source_id)
    if record.analysis is None:
        raise HTTPException(status_code=400, detail="This record has no analysis to flag")
    record.analysis.freshness = "pending_review"
    record.analysis.updated_at = utcnow()
    if record.review is None:
        record.review = ReviewState(record_id=record.id, state="needs_review", updated_at=utcnow())
    else:
        record.review.state = "needs_review"
        record.review.updated_at = utcnow()
    _audit(session, record.id, "analysis_marked_pending", {})
    session.commit()
    return record_to_dict(_get_record(session, source_type, source_id))


# --------------------------------------------------------------------------
# Metrics / brief
# --------------------------------------------------------------------------


@router.get("/metrics")
def metrics(
    person: str | None = None,
    source_type: str | None = None,
    route: str | None = None,
    review_state: str | None = None,
    text: str | None = None,
    override: str | None = None,
    freshness: str | None = None,
    search: str | None = None,
    date: str | None = None,
    session: Session = Depends(get_db),
):
    filters = {
        "person": person,
        "source_type": source_type,
        "route": route,
        "review_state": review_state,
        "text": text,
        "override": override,
        "freshness": freshness,
        "search": search,
        "date": date,
    }
    records = apply_filters(load_records(session), **filters)
    return compute_metrics(records, filters=filters)


@router.get("/brief")
def brief(session: Session = Depends(get_db)):
    records = load_records(session)
    m = compute_metrics(records)
    by_ref = {r.record_ref: r for r in records}
    ed = editorial()
    data = json.loads(json.dumps(ed))
    for section in data.get("brief", {}).get("sections", []):
        for item in section.get("items", []):
            record = by_ref.get(item["record_ref"])
            item["record"] = record_to_dict(record) if record else None
            verified = []
            for evidence in item.get("evidence", []):
                found = _verify_evidence(record, evidence) if record else False
                verified.append({**evidence, "verified": found})
            item["evidence"] = verified
    findings = data.get("findings", [])
    for finding in findings:
        record = by_ref.get(finding["evidence"].get("record_ref", ""))
        finding["verified"] = _verify_evidence(record, finding["evidence"]) if record else False
    return {
        "brief": data.get("brief"),
        "findings": findings,
        "rejected_decision": data.get("rejected_decision"),
        "metrics_notes": data.get("metrics_notes"),
        "metrics": m,
        "generated_from": "Manager brief narrative is pre-generated; activity numbers and evidence verification are computed at runtime.",
    }


def _verify_evidence(record: SourceRecord | None, evidence: dict) -> bool:
    if record is None:
        return False
    quote = (evidence.get("quote") or "").strip()
    if not quote:
        return False
    if evidence.get("kind") == "turn":
        turn_no = evidence.get("turn")
        for turn in record.turns or []:
            if turn.get("turn") == turn_no and quote in (turn.get("text") or ""):
                return True
        return False
    text = record.transcript_text or ""
    return quote in text


# --------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------


@router.get("/imports")
def imports(session: Session = Depends(get_db)):
    batches = session.scalars(select(ImportBatch).order_by(ImportBatch.imported_at.desc())).all()
    return {
        "datasets": _dataset_info(),
        "batches": [
            {
                "id": b.id,
                "batch_id": b.batch_id,
                "filename": b.filename,
                "delivery_revision": b.delivery_revision,
                "status": b.status,
                "imported_at": b.imported_at.isoformat(),
                "inserted": b.inserted,
                "updated": b.updated,
                "ignored": b.ignored,
                "errors": b.errors,
                "details": b.details,
            }
            for b in batches
        ],
        "current": {
            "records": session.query(SourceRecord).count(),
            "revisions": {
                rev: session.query(SourceRecord).filter(SourceRecord.applied_revision == rev).count()
                for rev in (1, 2)
            },
        },
    }


@router.post("/imports")
def run_import(payload: ImportRequest, session: Session = Depends(get_db)):
    path, revision = _read_dataset(payload.dataset)
    if payload.expected_revision is not None and payload.expected_revision != revision:
        raise HTTPException(status_code=400, detail="Expected revision does not match the selected dataset")
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        delivery = parse_delivery(raw, revision_override=revision)
    except ImportValidationError as exc:
        record_failed_import(session, batch_id="", filename=path.name, revision=revision, errors=exc.errors)
        raise HTTPException(status_code=422, detail={"errors": exc.errors}) from exc

    if payload.shuffle:
        rng = random.Random(20260821)
        rng.shuffle(delivery.records)

    batch = apply_delivery(session, delivery, filename=path.name)
    records = load_records(session)
    return {
        "batch": {
            "batch_id": batch.batch_id,
            "filename": batch.filename,
            "delivery_revision": batch.delivery_revision,
            "inserted": batch.inserted,
            "updated": batch.updated,
            "ignored": batch.ignored,
            "status": batch.status,
            "warnings": (batch.details or {}).get("warnings", []),
            "shuffled": payload.shuffle,
        },
        "metrics": compute_metrics(records)["totals"],
    }


@router.post("/imports/upload")
async def upload_import(
    file: UploadFile = File(...),
    expected_revision: int | None = None,
    session: Session = Depends(get_db),
):
    raw_bytes = await file.read()
    try:
        raw = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"File is not valid UTF-8 JSON: {exc}") from exc
    try:
        delivery = parse_delivery(raw, revision_override=expected_revision)
    except ImportValidationError as exc:
        record_failed_import(
            session,
            batch_id="",
            filename=file.filename or "upload.json",
            revision=expected_revision,
            errors=exc.errors,
        )
        raise HTTPException(status_code=422, detail={"errors": exc.errors}) from exc
    batch = apply_delivery(session, delivery, filename=file.filename or "upload.json")
    return {
        "batch_id": batch.batch_id,
        "delivery_revision": batch.delivery_revision,
        "inserted": batch.inserted,
        "updated": batch.updated,
        "ignored": batch.ignored,
    }


@router.post("/admin/reset")
def reset(session: Session = Depends(get_db)):
    result = reset_workspace(session)
    return {**result, "message": "Workspace reset. Import the initial delivery to start again."}


@router.post("/demo/load")
def demo_load(session: Session = Depends(get_db)):
    reset_workspace(session)
    initial_path, initial_rev = _read_dataset("initial")
    update_path, update_rev = _read_dataset("update")
    b1 = apply_delivery(session, parse_delivery(json.loads(initial_path.read_text()), revision_override=initial_rev), filename=initial_path.name)
    b2 = apply_delivery(session, parse_delivery(json.loads(update_path.read_text()), revision_override=update_rev), filename=update_path.name)
    records = load_records(session)
    return {
        "message": "Loaded the post-update demo state: initial delivery then update.",
        "batches": [
            {"filename": b1.filename, "inserted": b1.inserted, "updated": b1.updated, "ignored": b1.ignored},
            {"filename": b2.filename, "inserted": b2.inserted, "updated": b2.updated, "ignored": b2.ignored},
        ],
        "metrics": compute_metrics(records)["totals"],
    }


# --------------------------------------------------------------------------
# Exports
# --------------------------------------------------------------------------


@router.post("/replay")
def replay():
    return run_replay(DATA_DIR)


@router.get("/exports")
def exports(session: Session = Depends(get_db)):
    run = latest_export(session)
    return {
        "history": export_history(session),
        "current": run.manifest if run else None,
        "version": run.version if run else None,
        "created_at": run.created_at.isoformat() if run else None,
        "download": {
            "archive": "/api/exports/current/archive.zip",
            "manifest_json": "/api/exports/current/manifest.json",
            "manifest_csv": "/api/exports/current/manifest.csv",
        }
        if run
        else None,
    }


@router.post("/exports")
def create_export(session: Session = Depends(get_db)):
    if session.query(SourceRecord).count() == 0:
        raise HTTPException(status_code=409, detail="Import a delivery before generating an export")
    result = build_export(session)
    return result


@router.get("/exports/current/archive.zip")
def download_archive(session: Session = Depends(get_db)):
    run = latest_export(session)
    if run is None or not Path(run.archive_path).exists():
        raise HTTPException(status_code=404, detail="No export archive exists yet. Generate an export first.")
    return FileResponse(
        run.archive_path,
        media_type="application/zip",
        filename="revenue-intelligence-export.zip",
    )


@router.get("/exports/current/manifest.json")
def download_manifest_json(session: Session = Depends(get_db)):
    run = latest_export(session)
    if run is None:
        raise HTTPException(status_code=404, detail="No manifest exists yet. Generate an export first.")
    return FileResponse(_manifest_path(run), media_type="application/json", filename="manifest.json")


def _manifest_path(run: ExportRun, kind: str = "json") -> Path:
    base = Path(run.archive_path).parent / REPORTING_DATE / f"run-{run.version}" / "exports" / REPORTING_DATE
    return base / ("manifest.json" if kind == "json" else "manifest.csv")


@router.get("/exports/current/manifest.csv")
def download_manifest_csv(session: Session = Depends(get_db)):
    run = latest_export(session)
    if run is None:
        raise HTTPException(status_code=404, detail="No manifest exists yet. Generate an export first.")
    return FileResponse(_manifest_path(run, "csv"), media_type="text/csv", filename="manifest.csv")


# --------------------------------------------------------------------------
# Quality
# --------------------------------------------------------------------------


@router.get("/quality")
def quality(session: Session = Depends(get_db)):
    records = load_records(session)
    ed = editorial()

    def refs(items):
        return sorted(r.record_ref for r in items)

    no_text = [r for r in records if not r.has_usable_text]
    flag_but_empty = [
        r for r in records
        if r.source_type == "meeting" and r.has_transcript_flag is True and not r.has_usable_text
    ]
    call_flag_but_empty = [
        r for r in records
        if r.source_type == "call" and r.has_transcript_flag is True and not r.has_usable_text
    ]
    text_without_analysis = [r for r in records if r.has_usable_text and r.analysis is None]
    stale = [r for r in records if r.analysis and r.analysis.freshness in ("stale", "pending_review")]
    awaiting_but_reviewed = [
        r for r in records
        if not r.has_usable_text and r.review and r.review.state == "reviewed"
    ]
    missing_owner = [r for r in records if not r.owner_name]
    unverified_evidence = []
    for entry in all_analyses():
        record = next(
            (r for r in records
             if r.source_type == entry["source_type"] and r.source_id == entry["source_id"]),
            None,
        )
        if record is None:
            continue
        for evidence in entry["analysis"].get("evidence", []):
            if not _verify_evidence(record, evidence):
                unverified_evidence.append(
                    {"record_ref": record.record_ref, "evidence": evidence}
                )
    multi_route = [r for r in records if len(effective_routes(r)) > 1]
    unassigned_routes = [r for r in records if r.routing is None]

    return {
        "counts": {
            "records": len(records),
            "no_usable_text": len(no_text),
            "usable_text": len(records) - len(no_text),
            "meetings_flagged_without_turns": len(flag_but_empty),
            "calls_flagged_without_text": len(call_flag_but_empty),
            "text_without_analysis": len(text_without_analysis),
            "stale_or_pending_analysis": len(stale),
            "awaiting_text_but_reviewed": len(awaiting_but_reviewed),
            "missing_owner": len(missing_owner),
            "unverified_evidence": len(unverified_evidence),
            "multi_route_records": len(multi_route),
            "records_without_routing": len(unassigned_routes),
        },
        "lists": {
            "no_usable_text": refs(no_text),
            "meetings_flagged_without_turns": refs(flag_but_empty),
            "calls_flagged_without_text": refs(call_flag_but_empty),
            "text_without_analysis": refs(text_without_analysis),
            "stale_or_pending_analysis": refs(stale),
            "awaiting_text_but_reviewed": refs(awaiting_but_reviewed),
            "missing_owner": refs(missing_owner),
            "multi_route_records": refs(multi_route),
            "records_without_routing": refs(unassigned_routes),
        },
        "unverified_evidence": unverified_evidence,
        "notes": [
            "A meeting can be flagged has_transcript=true and still return zero usable turns; that is a source condition, not an application error.",
            "Missing text is never counted as a failed conversation and never receives a substantive analysis.",
            "All 44 records carry an intake/review state even when analysis is impossible.",
        ],
        "metrics_notes": ed.get("metrics_notes", []),
    }
