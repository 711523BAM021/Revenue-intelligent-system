"""Metric computation. Everything here reads the database; nothing is hardcoded."""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import REPORTING_DATE, REPORTING_TZ
from .ingest import effective_routes
from .models import SourceRecord
from .taxonomy import ROUTE_LABELS, ROUTE_ORDER, REVIEW_LABELS


def load_records(session: Session) -> list[SourceRecord]:
    stmt = (
        select(SourceRecord)
        .options(
            selectinload(SourceRecord.analysis),
            selectinload(SourceRecord.routing),
            selectinload(SourceRecord.review),
            selectinload(SourceRecord.override),
        )
        .order_by(SourceRecord.started_at_utc.desc(), SourceRecord.record_ref)
    )
    return list(session.scalars(stmt).all())


def apply_filters(
    records: list[SourceRecord],
    *,
    person: str | None = None,
    source_type: str | None = None,
    route: str | None = None,
    review_state: str | None = None,
    text: str | None = None,
    override: str | None = None,
    freshness: str | None = None,
    search: str | None = None,
    date: str | None = None,
) -> list[SourceRecord]:
    out = []
    needle = (search or "").strip().lower()
    for record in records:
        if person and record.owner_name != person:
            continue
        if source_type and record.source_type != source_type:
            continue
        if date and record.activity_date != date:
            continue
        if route and route not in effective_routes(record):
            continue
        if review_state:
            state = record.review.state if record.review else None
            if review_state == "needs_review":
                if state not in ("needs_review", "awaiting_text"):
                    continue
            elif state != review_state:
                continue
        if text == "usable" and not record.has_usable_text:
            continue
        if text == "missing" and record.has_usable_text:
            continue
        if override == "yes" and record.override is None:
            continue
        if override == "no" and record.override is not None:
            continue
        if freshness:
            current = record.analysis.freshness if record.analysis else "none"
            if freshness == "none" and record.analysis is not None:
                continue
            if freshness != "none" and current != freshness:
                continue
        if needle:
            haystack = " ".join(
                filter(
                    None,
                    [
                        record.record_ref,
                        record.title,
                        record.owner_name,
                        record.source_id,
                        record.transcript_text,
                        " ".join(t.get("text", "") for t in (record.turns or [])),
                    ],
                )
            ).lower()
            if needle not in haystack:
                continue
        out.append(record)
    return out


def compute_metrics(records: list[SourceRecord], *, filters: dict | None = None) -> dict:
    total = len(records)
    calls = [r for r in records if r.source_type == "call"]
    meetings = [r for r in records if r.source_type == "meeting"]
    usable = [r for r in records if r.has_usable_text]
    usable_calls = [r for r in calls if r.has_usable_text]
    usable_meetings = [r for r in meetings if r.has_usable_text]

    def pct(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator * 100, 1) if denominator else None

    review_counts = Counter((r.review.state if r.review else "unreviewed") for r in records)
    needs_review = sum(
        1 for r in records if (r.review.state if r.review else None) in ("needs_review", "awaiting_text")
    )
    awaiting_text = sum(
        1 for r in records if not r.has_usable_text
    )

    effective_counter: Counter[str] = Counter()
    suggested_counter: Counter[str] = Counter()
    multi_route = 0
    overridden = 0
    for record in records:
        eff = effective_routes(record)
        for route in eff:
            effective_counter[route] += 1
        for route in record.routing.suggested_routes if record.routing else []:
            suggested_counter[route] += 1
        if len(eff) > 1:
            multi_route += 1
        if record.override is not None:
            overridden += 1

    connected = [r for r in calls if r.is_connected is True]
    disconnected = [r for r in calls if r.is_connected is False]
    unknown = [r for r in calls if r.is_connected is None]

    by_day: dict[str, dict] = defaultdict(lambda: {"calls": 0, "meetings": 0, "records": 0})
    for record in records:
        key = record.activity_date or "unknown"
        by_day[key]["records"] += 1
        by_day[key]["calls" if record.source_type == "call" else "meetings"] += 1

    reps: dict[str, dict] = defaultdict(lambda: {"calls": 0, "usable_text": 0})
    organisers: dict[str, dict] = defaultdict(lambda: {"meetings": 0, "usable_text": 0})
    unassigned = {"calls": 0, "meetings": 0}
    for record in calls:
        if record.owner_name:
            reps[record.owner_name]["calls"] += 1
            reps[record.owner_name]["usable_text"] += 1 if record.has_usable_text else 0
        else:
            unassigned["calls"] += 1
    for record in meetings:
        if record.owner_name:
            organisers[record.owner_name]["meetings"] += 1
            organisers[record.owner_name]["usable_text"] += 1 if record.has_usable_text else 0
        else:
            unassigned["meetings"] += 1

    freshness_counts = Counter(
        (r.analysis.freshness if r.analysis else "none") for r in records
    )
    origin_counts = Counter((r.analysis.origin if r.analysis else "none") for r in records)

    outcomes = Counter(r.source_outcome for r in calls if r.source_outcome)

    return {
        "filters": filters or {},
        "reporting": {
            "date": REPORTING_DATE,
            "timezone": REPORTING_TZ,
            "label": "Selected records - 21 Aug 2026 (IST)",
        },
        "totals": {
            "records": total,
            "calls": len(calls),
            "meetings": len(meetings),
            "usable_text": len(usable),
            "usable_calls": len(usable_calls),
            "usable_meetings": len(usable_meetings),
            "coverage_pct": pct(len(usable), total),
            "coverage_denominator": total,
            "missing_text": total - len(usable),
            "needs_review": needs_review,
            "awaiting_text": awaiting_text,
            "manual_overrides": overridden,
            "multi_route_records": multi_route,
            "route_assignments": sum(effective_counter.values()),
        },
        "review_states": [
            {"state": key, "label": REVIEW_LABELS.get(key, key), "count": review_counts.get(key, 0)}
            for key in ["unreviewed", "needs_review", "reviewed", "awaiting_text"]
        ],
        "routes": {
            "effective": [
                {
                    "route": key,
                    "label": ROUTE_LABELS[key],
                    "count": effective_counter.get(key, 0),
                    "suggested_count": suggested_counter.get(key, 0),
                }
                for key in ROUTE_ORDER
            ],
            "assignments": sum(effective_counter.values()),
            "records": total,
            "multi_route_records": multi_route,
        },
        "activity_by_day": [
            {"date": key, **value} for key, value in sorted(by_day.items())
        ],
        "call_reps": sorted(
            [{"name": k, **v} for k, v in reps.items()], key=lambda x: (-x["calls"], x["name"])
        ),
        "meeting_organisers": sorted(
            [{"name": k, **v} for k, v in organisers.items()],
            key=lambda x: (-x["meetings"], x["name"]),
        ),
        "unassigned": unassigned,
        "connection": {
            "connected": len(connected),
            "disconnected": len(disconnected),
            "unknown": len(unknown),
            "denominator": len(connected) + len(disconnected),
            "rate_pct": pct(len(connected), len(connected) + len(disconnected)),
            "calls_total": len(calls),
        },
        "source_outcomes": [
            {"outcome": k, "count": v} for k, v in outcomes.most_common()
        ],
        "freshness": [
            {"state": k, "count": v}
            for k, v in freshness_counts.most_common()
        ],
        "analysis_origin": [
            {"origin": k, "count": v} for k, v in origin_counts.most_common()
        ],
    }
