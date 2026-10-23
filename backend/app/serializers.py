from __future__ import annotations

from .ingest import effective_routes
from .models import SourceRecord
from .taxonomy import PROCESSING_LABELS, REVIEW_LABELS, ROUTE_LABELS

FRESHNESS_LABELS = {
    "current": "Current",
    "stale": "Stale - source text changed",
    "pending_review": "Pending manager review",
    "unavailable": "Unavailable - no usable text",
    "missing": "Missing",
    "none": "No analysis",
}

ORIGIN_LABELS = {
    "pre_generated": "Pre-generated analysis",
    "rules_derived": "Rules-derived provisional",
    "human_assisted": "Manager-authored",
    "none": "None",
}

METHOD_LABELS = {
    "pre_generated_analysis": "Pre-generated analysis",
    "deterministic_rules": "Deterministic rules",
}


def processing_state(record: SourceRecord) -> str:
    if record.has_usable_text:
        return "complete"
    if record.source_type == "meeting" and record.has_transcript_flag is True:
        return "awaiting_transcript"
    return "text_unavailable"


def analysis_freshness(record: SourceRecord) -> str:
    if not record.has_usable_text:
        return "unavailable"
    if record.analysis is None:
        return "missing"
    return record.analysis.freshness


def record_to_dict(record: SourceRecord, *, include_transcript: bool = False) -> dict:
    suggested = list(record.routing.suggested_routes) if record.routing else ["needs_review"]
    effective = effective_routes(record)
    review = record.review
    proc = processing_state(record)
    freshness = analysis_freshness(record)
    override = record.override

    data = {
        "id": record.id,
        "source_type": record.source_type,
        "source_id": record.source_id,
        "record_ref": record.record_ref,
        "title": record.title,
        "started_at_utc": record.started_at_utc,
        "started_at_local": record.started_at_local,
        "activity_date": record.activity_date,
        "owner_name": record.owner_name,
        "owner_kind": record.owner_kind,
        "owner_role_label": (
            "Call representative" if record.owner_kind == "call_representative" else "Meeting organiser"
        ),
        "owner_email": record.owner_email,
        "direction": record.direction,
        "duration_seconds": record.duration_seconds,
        "source_outcome": record.source_outcome,
        "is_connected": record.is_connected,
        "is_conversation": record.is_conversation,
        "recording_status": record.recording_status,
        "has_transcript_flag": record.has_transcript_flag,
        "has_usable_text": record.has_usable_text,
        "unavailable_reason": record.unavailable_reason,
        "applied_revision": record.applied_revision,
        "first_revision": record.first_revision,
        "last_batch_id": record.last_batch_id,
        "last_revision_changed_at": record.last_revision_changed_at.isoformat()
        if record.last_revision_changed_at
        else None,
        "processing_state": proc,
        "processing_label": PROCESSING_LABELS.get(proc, proc),
        "suggested_routes": suggested,
        "suggested_route_labels": [ROUTE_LABELS.get(r, r) for r in suggested],
        "effective_routes": effective,
        "effective_route_labels": [ROUTE_LABELS.get(r, r) for r in effective],
        "manual_override": override is not None,
        "override": {
            "routes": override.effective_routes,
            "reason": override.reason,
            "updated_at": override.updated_at.isoformat(),
        }
        if override
        else None,
        "review_state": review.state if review else "unreviewed",
        "review_label": REVIEW_LABELS.get(review.state if review else "unreviewed", "Not yet reviewed"),
        "review_note": review.note if review else None,
        "review_updated_at": review.updated_at.isoformat() if review else None,
        "analysis_freshness": freshness,
        "analysis_freshness_label": FRESHNESS_LABELS.get(freshness, freshness),
        "routing_method": record.routing.method if record.routing else None,
        "routing_method_label": METHOD_LABELS.get(record.routing.method, "None")
        if record.routing
        else "None",
        "routing_rationale": record.routing.rationale if record.routing else None,
        "routing_trace": record.routing.trace if record.routing else [],
        "routing_computed_at": record.routing.computed_at.isoformat() if record.routing else None,
    }

    if record.analysis:
        data["analysis"] = {
            "content": record.analysis.content,
            "origin": record.analysis.origin,
            "origin_label": ORIGIN_LABELS.get(record.analysis.origin, record.analysis.origin),
            "author": record.analysis.author,
            "freshness": record.analysis.freshness,
            "freshness_label": FRESHNESS_LABELS.get(record.analysis.freshness, record.analysis.freshness),
            "source_revision": record.analysis.source_revision,
            "engine_version": record.analysis.engine_version,
            "generated_at": record.analysis.generated_at.isoformat(),
            "updated_at": record.analysis.updated_at.isoformat(),
        }
    else:
        data["analysis"] = None

    if include_transcript:
        data["transcript_text"] = record.transcript_text
        data["turns"] = record.turns

    return data
