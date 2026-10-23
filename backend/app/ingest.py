"""Revision-aware import engine.

Identity is always the pair (source_type, source_id). A delivery carries one
revision for all of its records; a newer revision replaces the record's entire
source and transcript payload (including nulls), an equal or older revision is
ignored. Manual routing decisions live in a separate table and are never
touched by an import.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import REPORTING_TZ
from .corpus import corpus_analysis
from .models import (
    Analysis,
    AnalysisHistory,
    AuditEvent,
    ImportBatch,
    ReviewState,
    RouteOverride,
    RoutingDecision,
    SourceRecord,
    utcnow,
)
from .routing_rules import ENGINE_VERSION, suggest_routes
from .taxonomy import normalise_routes

LOCAL_TZ = ZoneInfo(REPORTING_TZ)


class ImportValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass
class NormalisedRecord:
    source_type: str
    source_id: str
    record_ref: str
    payload: dict
    transcript_payload: dict | None
    title: str | None
    started_at_utc: str | None
    activity_date: str | None
    started_at_local: str | None
    owner_name: str | None
    owner_kind: str
    owner_email: str | None
    direction: str | None
    duration_seconds: int | None
    source_outcome: str | None
    is_connected: bool | None
    is_conversation: bool | None
    recording_status: str | None
    has_transcript_flag: bool | None
    transcript_text: str | None
    turns: list[dict] | None
    unavailable_reason: str | None
    has_usable_text: bool
    text_hash: str | None


@dataclass
class ParsedDelivery:
    revision: int
    batch_id: str
    records: list[NormalisedRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _parse_dt(value: Any, label: str, errors: list[str]) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append(f"{label}: timestamp must be an ISO string, got {type(value).__name__}")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label}: unparseable timestamp {value!r}")
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _blank(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def _normalise_turns(raw: Any, label: str, errors: list[str]) -> list[dict] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        errors.append(f"{label}: transcript turns must be an array or null")
        return None
    turns: list[dict] = []
    for index, turn in enumerate(raw):
        if not isinstance(turn, dict):
            errors.append(f"{label}: turn {index + 1} is not an object")
            continue
        text = turn.get("text")
        if text is not None and not isinstance(text, str):
            errors.append(f"{label}: turn {index + 1} text must be a string")
            text = None
        turns.append(
            {
                "turn": index + 1,
                "speaker": turn.get("speaker"),
                "text": text if isinstance(text, str) else "",
                "starts_at_seconds": turn.get("starts_at_seconds"),
                "timecode": turn.get("timecode"),
            }
        )
    return turns


def _hash_text(source_type: str, text: str | None, turns: list[dict] | None) -> str | None:
    if source_type == "call":
        if not text:
            return None
        basis = "call\n" + text.strip()
    else:
        if not turns:
            return None
        joined = "\n".join(f"{t['speaker'] or ''}:{t['text']}" for t in turns if t["text"].strip())
        if not joined:
            return None
        basis = "meeting\n" + joined
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def normalise_record(raw: Any, index: int, revision: int, errors: list[str], warnings: list[str]) -> NormalisedRecord | None:
    label = f"records[{index}]"
    if not isinstance(raw, dict):
        errors.append(f"{label}: must be an object")
        return None

    source_type = raw.get("source_type")
    if source_type not in ("call", "meeting"):
        errors.append(f"{label}: source_type must be 'call' or 'meeting', got {source_type!r}")
        return None

    source_id = raw.get("source_id")
    if not isinstance(source_id, str) or not source_id.strip():
        errors.append(f"{label}: source_id must be a non-empty string")
        return None
    source_id = source_id.strip()

    record_ref = raw.get("record_ref")
    if not isinstance(record_ref, str) or not record_ref.strip():
        errors.append(f"{label}: record_ref must be a non-empty string")
        return None
    record_ref = record_ref.strip()

    payload = raw.get("payload")
    if not isinstance(payload, dict):
        errors.append(f"{label}: payload must be an object")
        return None

    payload_id = payload.get("id")
    if payload_id is not None and str(payload_id) != source_id:
        errors.append(
            f"{label}: source_id {source_id!r} does not match payload.id {payload_id!r}"
        )
        return None

    transcript_payload = raw.get("transcript_payload")
    if transcript_payload is not None and not isinstance(transcript_payload, dict):
        errors.append(f"{label}: transcript_payload must be an object or null")
        return None

    if source_type == "meeting":
        if transcript_payload is not None:
            mtg_id = transcript_payload.get("meeting_id")
            if mtg_id is not None and str(mtg_id) != source_id:
                errors.append(
                    f"{label}: transcript_payload.meeting_id {mtg_id!r} does not match source_id"
                )
                return None
    elif transcript_payload is not None:
        warnings.append(f"{label}: call carried a transcript_payload; ignored for calls")

    started_raw = payload.get("started_at") if source_type == "call" else payload.get("starts_at")
    started = _parse_dt(started_raw, f"{label}.started_at", errors)
    started_utc = started.astimezone(timezone.utc) if started else None
    started_local = started.astimezone(LOCAL_TZ) if started else None

    transcript_text: str | None = None
    turns: list[dict] | None = None
    unavailable_reason: str | None = None

    if source_type == "call":
        raw_transcript = payload.get("transcript")
        if raw_transcript is not None and not isinstance(raw_transcript, str):
            errors.append(f"{label}: payload.transcript must be a string or null")
            return None
        if isinstance(raw_transcript, str) and raw_transcript.strip():
            transcript_text = raw_transcript.strip()
        has_usable_text = transcript_text is not None
        owner_name = payload.get("rep_name") or payload.get("rep_email")
        owner_email = payload.get("rep_email")
        owner_kind = "call_representative"
        title = None
        source_outcome = payload.get("observed_outcome")
        recording_status = payload.get("classification_status")
    else:
        turns = _normalise_turns(
            transcript_payload.get("turns") if transcript_payload else None,
            f"{label}.transcript_payload.turns",
            errors,
        )
        unavailable_reason = (
            transcript_payload.get("unavailable_reason") if transcript_payload else None
        )
        if unavailable_reason is not None and not isinstance(unavailable_reason, str):
            errors.append(f"{label}: unavailable_reason must be a string or null")
        has_usable_text = bool(turns) and any(t["text"].strip() for t in turns or [])
        owner_email = payload.get("organizer_email")
        owner_name = owner_email
        owner_kind = "meeting_organiser"
        title = payload.get("title")
        source_outcome = None
        recording_status = payload.get("recording_status")

    text_hash = _hash_text(source_type, transcript_text, turns)

    duration = payload.get("duration_seconds")
    if duration is not None and not isinstance(duration, (int, float)):
        errors.append(f"{label}: duration_seconds must be numeric or null")
        duration = None

    return NormalisedRecord(
        source_type=source_type,
        source_id=source_id,
        record_ref=record_ref,
        payload=payload,
        transcript_payload=transcript_payload if source_type == "meeting" else None,
        title=title if isinstance(title, str) else None,
        started_at_utc=started_utc.isoformat() if started_utc else None,
        activity_date=started_local.date().isoformat() if started_local else None,
        started_at_local=started_local.isoformat() if started_local else None,
        owner_name=owner_name if isinstance(owner_name, str) else None,
        owner_kind=owner_kind,
        owner_email=owner_email if isinstance(owner_email, str) else None,
        direction=payload.get("direction") if source_type == "call" else None,
        duration_seconds=int(duration) if isinstance(duration, (int, float)) else None,
        source_outcome=source_outcome if isinstance(source_outcome, str) else None,
        is_connected=payload.get("is_connected") if isinstance(payload.get("is_connected"), bool) else None,
        is_conversation=payload.get("is_conversation") if isinstance(payload.get("is_conversation"), bool) else None,
        recording_status=recording_status if isinstance(recording_status, str) else None,
        has_transcript_flag=payload.get("has_transcript") if isinstance(payload.get("has_transcript"), bool) else None,
        transcript_text=transcript_text,
        turns=turns,
        unavailable_reason=unavailable_reason,
        has_usable_text=has_usable_text,
        text_hash=text_hash,
    )


def parse_delivery(raw: Any, *, revision_override: int | None = None) -> ParsedDelivery:
    errors: list[str] = []
    warnings: list[str] = []

    if isinstance(raw, list):
        errors.append("Delivery must be a JSON object with a 'records' array, not a bare array")
        raise ImportValidationError(errors)

    if not isinstance(raw, dict):
        raise ImportValidationError(["Delivery must be a JSON object"])

    revision = raw.get("revision", revision_override)
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ImportValidationError(
            [f"Envelope 'revision' must be a positive integer, got {raw.get('revision')!r}"]
        )
    if revision_override is not None and revision != revision_override:
        errors.append(
            f"Envelope revision {revision} does not match the expected delivery revision {revision_override}"
        )

    records_raw = raw.get("records")
    if not isinstance(records_raw, list):
        raise ImportValidationError(["Envelope must contain a 'records' array"])
    if not records_raw:
        raise ImportValidationError(["Envelope 'records' array is empty"])

    batch_id = raw.get("batch_id")
    if not isinstance(batch_id, str) or not batch_id.strip():
        batch_id = f"batch-{uuid.uuid4().hex[:12]}"
        warnings.append("Envelope had no batch_id; generated one for the import record")

    delivery = ParsedDelivery(revision=revision, batch_id=batch_id)
    seen: dict[tuple[str, str], int] = {}

    for index, item in enumerate(records_raw):
        normalised = normalise_record(item, index, revision, errors, warnings)
        if normalised is None:
            continue
        key = (normalised.source_type, normalised.source_id)
        if key in seen:
            errors.append(
                f"Duplicate source identity {key} at records[{seen[key]}] and records[{index}] "
                "within the same delivery"
            )
            continue
        seen[key] = index
        delivery.records.append(normalised)

    delivery.errors = errors
    delivery.warnings = warnings
    if errors:
        raise ImportValidationError(errors)
    return delivery


# --------------------------------------------------------------------------
# Analysis binding
# --------------------------------------------------------------------------


def _rules_content(record: SourceRecord, suggestion: dict) -> dict:
    return {
        "summary": (
            "No pre-generated analysis is available for this text. The routing engine "
            "matched the signals below; a manager should confirm or replace this."
        ),
        "why_it_matters": suggestion["rationale"],
        "evidence": [],
        "risks": [],
        "opportunities": [],
        "uncertainties": [
            "Analysis was derived by deterministic keyword rules, not read by an analyst.",
        ],
        "next_action": "Open the conversation and confirm the route.",
        "action_owner": None,
        "owner_basis": None,
        "suggested_routes": suggestion["routes"],
        "route_rationale": suggestion["rationale"],
        "route_trace": suggestion["trace"],
        "review_status": "needs_review",
        "analysis_basis": "Deterministic rules over the supplied text",
    }


def _archive_analysis(session: Session, record: SourceRecord, reason: str) -> None:
    if not record.analysis:
        return
    session.add(
        AnalysisHistory(
            record_id=record.id,
            content=record.analysis.content,
            origin=record.analysis.origin,
            freshness=record.analysis.freshness,
            source_revision=record.analysis.source_revision,
            text_hash=record.analysis.text_hash,
            archive_reason=reason,
        )
    )


def _set_review(session: Session, record: SourceRecord, state: str, note: str) -> None:
    if record.review is None:
        record.review = ReviewState(record_id=record.id, state=state, note=note, updated_at=utcnow())
    else:
        record.review.state = state
        record.review.note = note
        record.review.updated_at = utcnow()


def _set_routing(session: Session, record: SourceRecord, analysis: Analysis | None, suggestion: dict) -> None:
    if analysis is not None and analysis.origin != "rules_derived":
        content = analysis.content
        routes = normalise_routes(content.get("suggested_routes") or suggestion["routes"])
        method = "pre_generated_analysis"
        rationale = content.get("route_rationale") or suggestion["rationale"]
        trace = content.get("route_trace") or suggestion["trace"]
    else:
        routes = normalise_routes(suggestion["routes"])
        method = suggestion["method"]
        rationale = suggestion["rationale"]
        trace = suggestion["trace"]

    if record.routing is None:
        record.routing = RoutingDecision(
            record_id=record.id,
            suggested_routes=routes,
            method=method,
            rationale=rationale,
            trace=trace,
            text_hash=record.text_hash,
            computed_at=utcnow(),
        )
    else:
        record.routing.suggested_routes = routes
        record.routing.method = method
        record.routing.rationale = rationale
        record.routing.trace = trace
        record.routing.text_hash = record.text_hash
        record.routing.computed_at = utcnow()


def _build_analysis(session: Session, record: SourceRecord, *, changed: bool) -> Analysis | None:
    """Create/replace the analysis for the current source state."""
    existing = record.analysis
    suggestion = suggest_routes(
        source_type=record.source_type,
        text=record.transcript_text
        or "\n".join(t["text"] for t in (record.turns or []) if t["text"]),
        has_usable_text=record.has_usable_text,
        source_outcome=record.source_outcome,
        is_connected=record.is_connected,
    )

    if not record.has_usable_text:
        if existing is not None:
            _archive_analysis(session, record, "Source text became unavailable")
            session.delete(existing)
            session.flush()
            record.analysis = None
        # Even a record with no text needs a route decision (intake review) and a
        # stored trace, so downstream filters and exports are consistent.
        _set_routing(session, record, None, suggestion)
        return None
    entry = corpus_analysis(record.source_type, record.source_id)

    if changed and existing is not None:
        if existing.origin == "human_assisted":
            # Never erase a human judgment; flag it instead.
            _archive_analysis(session, record, "New source revision invalidated this analysis")
            existing.freshness = "stale"
            existing.updated_at = utcnow()
            _set_review(
                session,
                record,
                "needs_review",
                "New source text arrived in this revision. The manager-authored analysis "
                "was written against the earlier text and is now stale.",
            )
            _set_routing(session, record, existing, suggestion)
            return existing

        _archive_analysis(session, record, "New source revision replaced the analysed text")
        content = entry["analysis"] if entry else _rules_content(record, suggestion)
        origin = "pre_generated" if entry else "rules_derived"
        if existing is None:
            existing = Analysis(record_id=record.id, content=content, origin=origin,
                                freshness="current", source_revision=record.applied_revision,
                                text_hash=record.text_hash, engine_version=ENGINE_VERSION)
            record.analysis = existing
        else:
            existing.content = content
            existing.origin = origin
            existing.freshness = "current" if entry else "pending_review"
            existing.source_revision = record.applied_revision
            existing.text_hash = record.text_hash
            existing.author = None
            existing.updated_at = utcnow()
        _set_review(
            session,
            record,
            "needs_review",
            f"Source text changed at revision {record.applied_revision}. "
            + ("Analysis refreshed from the pre-generated library; confirm the route."
               if entry else "A provisional rules-derived analysis was generated for review."),
        )
        _set_routing(session, record, existing, suggestion)
        return existing

    if existing is not None:
        # Same text: keep the analysis, but record that it reflects this revision.
        existing.source_revision = record.applied_revision
        existing.text_hash = record.text_hash
        _set_routing(session, record, existing, suggestion)
        return existing

    if entry:
        analysis = Analysis(
            record_id=record.id,
            content=entry["analysis"],
            origin="pre_generated",
            freshness="current",
            source_revision=record.applied_revision,
            text_hash=record.text_hash,
            engine_version=ENGINE_VERSION,
        )
        record.analysis = analysis
        flagged = (entry["analysis"].get("review_status") == "needs_review"
                   or "needs_review" in (entry["analysis"].get("suggested_routes") or []))
        if record.review is None or record.review.state in ("unreviewed", "awaiting_text"):
            _set_review(
                session,
                record,
                "needs_review" if flagged else "unreviewed",
                entry["analysis"].get("review_note")
                or "Pre-generated analysis loaded; awaiting manager review.",
            )
    else:
        analysis = Analysis(
            record_id=record.id,
            content=_rules_content(record, suggestion),
            origin="rules_derived",
            freshness="current",
            source_revision=record.applied_revision,
            text_hash=record.text_hash,
            engine_version=ENGINE_VERSION,
        )
        record.analysis = analysis
        if record.review is None or record.review.state == "awaiting_text":
            _set_review(
                session,
                record,
                "unreviewed",
                "Usable text is now available; awaiting manager review."
                if record.review is not None
                else "Awaiting manager review.",
            )

    _set_routing(session, record, record.analysis, suggestion)
    return record.analysis


# --------------------------------------------------------------------------
# Apply
# --------------------------------------------------------------------------


def _apply_fields(record: SourceRecord, incoming: NormalisedRecord, revision: int, batch_id: str) -> None:
    record.record_ref = incoming.record_ref
    record.applied_revision = revision
    record.title = incoming.title
    record.started_at_utc = incoming.started_at_utc
    record.activity_date = incoming.activity_date
    record.started_at_local = incoming.started_at_local
    record.owner_name = incoming.owner_name
    record.owner_email = incoming.owner_email
    record.owner_kind = incoming.owner_kind
    record.direction = incoming.direction
    record.duration_seconds = incoming.duration_seconds
    record.source_outcome = incoming.source_outcome
    record.is_connected = incoming.is_connected
    record.is_conversation = incoming.is_conversation
    record.recording_status = incoming.recording_status
    record.has_transcript_flag = incoming.has_transcript_flag
    record.transcript_text = incoming.transcript_text
    record.turns = incoming.turns
    record.unavailable_reason = incoming.unavailable_reason
    record.has_usable_text = incoming.has_usable_text
    record.text_hash = incoming.text_hash
    record.raw_payload = incoming.payload
    record.raw_transcript_payload = incoming.transcript_payload
    record.last_batch_id = batch_id
    record.updated_at = utcnow()
    record.last_revision_changed_at = utcnow()


def apply_delivery(
    session: Session,
    delivery: ParsedDelivery,
    *,
    filename: str,
    fail_batch_on_error: bool = True,
) -> ImportBatch:
    """Apply a validated delivery in one transaction."""
    batch = ImportBatch(
        batch_id=delivery.batch_id,
        filename=filename,
        delivery_revision=delivery.revision,
        status="applied",
        errors=[],
        details={"warnings": delivery.warnings},
    )
    inserted = updated = ignored = 0
    per_record: list[dict] = []

    try:
        for incoming in delivery.records:
            existing = session.scalar(
                select(SourceRecord).where(
                    SourceRecord.source_type == incoming.source_type,
                    SourceRecord.source_id == incoming.source_id,
                )
            )
            if existing is None:
                record = SourceRecord(
                    source_type=incoming.source_type,
                    source_id=incoming.source_id,
                    record_ref=incoming.record_ref,
                    applied_revision=delivery.revision,
                    first_revision=delivery.revision,
                    owner_kind=incoming.owner_kind,
                    raw_payload=incoming.payload,
                )
                _apply_fields(record, incoming, delivery.revision, delivery.batch_id)
                session.add(record)
                session.flush()
                _build_analysis(session, record, changed=False)
                if not incoming.has_usable_text:
                    _set_review(
                        session,
                        record,
                        "awaiting_text",
                        "No usable supplied conversation text in this revision. "
                        "Nothing substantive can be analysed until text is supplied.",
                    )
                session.add(
                    AuditEvent(
                        record_id=record.id,
                        kind="record_inserted",
                        detail={
                            "revision": delivery.revision,
                            "batch_id": delivery.batch_id,
                            "record_ref": incoming.record_ref,
                        },
                    )
                )
                inserted += 1
                per_record.append(
                    {"record_ref": incoming.record_ref, "action": "inserted", "revision": delivery.revision}
                )
            elif delivery.revision > existing.applied_revision:
                previous_revision = existing.applied_revision
                old_hash = existing.text_hash
                old_revision = existing.record_ref
                _apply_fields(existing, incoming, delivery.revision, delivery.batch_id)
                session.flush()
                changed_text = old_hash != existing.text_hash
                _build_analysis(session, existing, changed=changed_text)
                if not existing.has_usable_text:
                    _set_review(
                        session,
                        existing,
                        "awaiting_text",
                        "No usable supplied conversation text in this revision.",
                    )
                elif changed_text:
                    # A new source text must be visibly flagged, even when this is
                    # the first text ever supplied for the record.
                    _set_review(
                        session,
                        existing,
                        "needs_review",
                        f"Source text changed at revision {delivery.revision}. "
                        + (
                            "Analysis refreshed from the pre-generated library; confirm the route."
                            if existing.analysis and existing.analysis.origin == "pre_generated"
                            else "A provisional rules-derived analysis was generated for review."
                        ),
                    )
                session.add(
                    AuditEvent(
                        record_id=existing.id,
                        kind="record_updated",
                        detail={
                            "from_revision": previous_revision,
                            "to_revision": delivery.revision,
                            "batch_id": delivery.batch_id,
                            "text_changed": changed_text,
                            "previous_record_ref": old_revision,
                        },
                    )
                )
                updated += 1
                per_record.append(
                    {
                        "record_ref": incoming.record_ref,
                        "action": "updated",
                        "from_revision": previous_revision,
                        "to_revision": delivery.revision,
                        "text_changed": changed_text,
                    }
                )
            else:
                ignored += 1
                per_record.append(
                    {
                        "record_ref": incoming.record_ref,
                        "action": "ignored",
                        "stored_revision": existing.applied_revision,
                        "incoming_revision": delivery.revision,
                    }
                )

        batch.inserted = inserted
        batch.updated = updated
        batch.ignored = ignored
        batch.details = {"warnings": delivery.warnings, "records": per_record}
        session.add(batch)
        session.commit()
    except Exception as exc:  # noqa: BLE001 - any failure must roll back cleanly
        session.rollback()
        if not fail_batch_on_error:
            raise
        failure = ImportBatch(
            batch_id=delivery.batch_id,
            filename=filename,
            delivery_revision=delivery.revision,
            status="failed",
            inserted=0,
            updated=0,
            ignored=0,
            errors=[f"Import aborted and rolled back: {exc}"],
            details={"records": per_record},
        )
        session.add(failure)
        session.commit()
        raise

    return batch


def record_failed_import(session: Session, *, batch_id: str, filename: str, revision: int | None, errors: list[str]) -> None:
    session.add(
        ImportBatch(
            batch_id=batch_id or f"batch-{uuid.uuid4().hex[:12]}",
            filename=filename,
            delivery_revision=revision or 0,
            status="failed",
            errors=errors,
            details={},
        )
    )
    session.commit()


def load_dataset_file(path, expected_revision: int | None = None) -> ParsedDelivery:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return parse_delivery(raw, revision_override=expected_revision)


def import_dataset_file(session: Session, path, *, expected_revision: int | None = None) -> ImportBatch:
    try:
        delivery = load_dataset_file(path, expected_revision)
    except ImportValidationError as exc:
        record_failed_import(
            session,
            batch_id="",
            filename=path.name,
            revision=expected_revision,
            errors=exc.errors,
        )
        raise
    return apply_delivery(session, delivery, filename=path.name)


def reset_workspace(session: Session) -> dict:
    from .models import ExportRun

    for model in (
        AnalysisHistory,
        Analysis,
        RoutingDecision,
        RouteOverride,
        ReviewState,
        AuditEvent,
        SourceRecord,
        ImportBatch,
        ExportRun,
    ):
        session.query(model).delete()
    session.commit()
    return {"status": "reset", "records": 0}


def is_manual_override(record: SourceRecord) -> bool:
    return record.override is not None


def effective_routes(record: SourceRecord) -> list[str]:
    if record.override is not None:
        return list(record.override.effective_routes)
    if record.routing is not None:
        return list(record.routing.suggested_routes)
    return ["needs_review"]
