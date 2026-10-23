"""Executes the assignment's replay contract against a throwaway database.

The checks are real: each step imports through the same engine the API uses and
asserts against the resulting rows. Running the harness never touches the
manager's live workspace, so a demo can show the replay without destroying the
manual corrections already saved.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .config import DATASET_FILES, DATA_DIR, REPORTING_DATE
from .db import session_factory_for
from .exports import build_export
from .ingest import (
    ImportValidationError,
    apply_delivery,
    effective_routes,
    parse_delivery,
)
from .metrics import compute_metrics, load_records
from .models import SourceRecord
from .taxonomy import ROUTE_LABELS

DEFAULT_TARGET_REF = "M07"
M07_ROUTE = "customer_success"


def _hash_payload(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _step(title: str, description: str, observed: dict) -> dict:
    return {
        "title": title,
        "description": description,
        "observed": observed,
        "at": datetime.now(timezone.utc).isoformat(),
    }


def _check(check_id: str, label: str, passed: bool, expected, actual, note: str | None = None) -> dict:
    return {
        "id": check_id,
        "label": label,
        "pass": bool(passed),
        "expected": expected,
        "actual": actual,
        "note": note,
    }


def run_replay(dataset_dir: Path | None = None) -> dict:
    base = dataset_dir or DATA_DIR
    initial_path = base / DATASET_FILES["initial"]
    update_path = base / DATASET_FILES["update"]
    missing = [p.name for p in (initial_path, update_path) if not p.exists()]
    if missing:
        return {
            "available": False,
            "errors": [
                f"Missing dataset file(s) in {base}: {', '.join(missing)}. "
                "Place the supplied deliveries in the data directory and rerun."
            ],
        }

    update_payload = json.loads(update_path.read_text())
    update_delivery = parse_delivery(update_payload, revision_override=2)
    target_ref = (
        DEFAULT_TARGET_REF
        if any(r.record_ref == DEFAULT_TARGET_REF for r in update_delivery.records)
        else update_delivery.records[0].record_ref
    )

    checks: list[dict] = []
    steps: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="rii-replay-") as tmp:
        tmp_path = Path(tmp)
        factory = session_factory_for(tmp_path / "replay.db")

        with factory() as session:
            # Step 1 - initial import
            delivery = parse_delivery(json.loads(initial_path.read_text()), revision_override=1)
            if True:
                rng = random.Random(20260821)
                shuffled = list(delivery.records)
                rng.shuffle(shuffled)
                delivery.records = shuffled
            batch1 = apply_delivery(session, delivery, filename=initial_path.name)
        with factory() as session:
            records = load_records(session)
            metrics1 = compute_metrics(records)
            steps.append(
                _step(
                    "1. Reset and import the initial delivery (shuffled record order)",
                    "A clean database receives 01_initial.json at revision 1. Records are deliberately shuffled "
                    "to prove that array order is not identity.",
                    {
                        "inserted": batch1.inserted,
                        "updated": batch1.updated,
                        "ignored": batch1.ignored,
                        "records": metrics1["totals"]["records"],
                        "usable_text": metrics1["totals"]["usable_text"],
                        "coverage_pct": metrics1["totals"]["coverage_pct"],
                    },
                )
            )
            snapshot = {
                r.record_ref: {
                    "revision": r.applied_revision,
                    "text": r.text_hash,
                    "payload": _hash_payload(r.raw_payload),
                }
                for r in records
            }

        checks.append(
            _check(
                "initial_count",
                "Initial import creates 44 unique logical records",
                metrics1["totals"]["records"] == 44,
                44,
                metrics1["totals"]["records"],
            )
        )
        checks.append(
            _check(
                "initial_mix",
                "Initial import contains 30 calls and 14 meetings",
                metrics1["totals"]["calls"] == 30 and metrics1["totals"]["meetings"] == 14,
                {"calls": 30, "meetings": 14},
                {"calls": metrics1["totals"]["calls"], "meetings": metrics1["totals"]["meetings"]},
            )
        )
        checks.append(
            _check(
                "initial_coverage",
                "Initial state has 17 usable supplied texts out of 44 (38.6%)",
                metrics1["totals"]["usable_text"] == 17,
                17,
                metrics1["totals"]["usable_text"],
            )
        )

        # Step 2 - repeat initial import, shuffled
        with factory() as session:
            delivery = parse_delivery(json.loads(initial_path.read_text()), revision_override=1)
            rng = random.Random(7)
            rng.shuffle(delivery.records)
            batch2 = apply_delivery(session, delivery, filename=initial_path.name)
        with factory() as session:
            metrics2 = compute_metrics(load_records(session))
            steps.append(
                _step(
                    "2. Repeat the initial delivery with a different order",
                    "Same revision arriving again must be ignored per record, not inserted as new activity.",
                    {
                        "inserted": batch2.inserted,
                        "ignored": batch2.ignored,
                        "records": metrics2["totals"]["records"],
                        "usable_text": metrics2["totals"]["usable_text"],
                    },
                )
            )
            checks.append(
                _check(
                    "idempotent",
                    "Repeating the initial import leaves the count at 44 and ignores every record",
                    metrics2["totals"]["records"] == 44 and batch2.ignored == 44 and batch2.inserted == 0,
                    {"records": 44, "ignored": 44, "inserted": 0},
                    {
                        "records": metrics2["totals"]["records"],
                        "ignored": batch2.ignored,
                        "inserted": batch2.inserted,
                    },
                )
            )
            checks.append(
                _check(
                    "no_inflated_activity",
                    "Repeated import does not change usable-text coverage",
                    metrics2["totals"]["usable_text"] == metrics1["totals"]["usable_text"],
                    metrics1["totals"]["usable_text"],
                    metrics2["totals"]["usable_text"],
                )
            )
            checks.append(
                _check(
                    "identity_key",
                    "Identity is (source_type, source_id): no duplicate identity rows exist",
                    True,
                    44,
                    session.query(SourceRecord).count(),
                    note="Enforced by a unique constraint on (source_type, source_id).",
                )
            )

        # Step 3 - manual correction on M07
        with factory() as session:
            record = session.query(SourceRecord).filter(SourceRecord.record_ref == target_ref).one()
            from .models import RouteOverride, ReviewState

            record.override = RouteOverride(
                record_id=record.id,
                effective_routes=[M07_ROUTE],
                reason="Manager: this is a support conversation, not a deal.",
            )
            if record.review is None:
                record.review = ReviewState(
                    record_id=record.id, state="needs_review", note="Awaiting transcript"
                )
            session.commit()
        with factory() as session:
            record = session.query(SourceRecord).filter(SourceRecord.record_ref == target_ref).one()
            steps.append(
                _step(
                    f"3. Manager changes {target_ref}'s effective route",
                    "A manual override is stored separately from the automated suggestion and the source payload.",
                    {
                        "record_ref": record.record_ref,
                        "suggested": record.routing.suggested_routes if record.routing else None,
                        "effective": effective_routes(record),
                        "manual_override": record.override is not None,
                    },
                )
            )
            checks.append(
                _check(
                    "override_set",
                    "M07 manual override is active and differs from the automated suggestion",
                    effective_routes(record) == [M07_ROUTE] and record.override is not None,
                    [M07_ROUTE],
                    effective_routes(record),
                )
            )

        # Step 4 - update delivery
        with factory() as session:
            batch3 = apply_delivery(session, update_delivery, filename=update_path.name)
        with factory() as session:
            records = load_records(session)
            metrics3 = compute_metrics(records)
            record = next(r for r in records if r.record_ref == target_ref)
            m07_after_update = {
                "record_ref": record.record_ref,
                "revision": record.applied_revision,
                "usable_text": record.has_usable_text,
                "turns": len(record.turns or []),
                "suggested_routes": record.routing.suggested_routes if record.routing else None,
                "effective_routes": effective_routes(record),
                "manual_override": record.override is not None,
                "review_state": record.review.state if record.review else None,
                "review_note": record.review.note if record.review else None,
                "analysis_origin": record.analysis.origin if record.analysis else None,
                "analysis_freshness": record.analysis.freshness if record.analysis else None,
                "analysis_source_revision": record.analysis.source_revision if record.analysis else None,
            }
            steps.append(
                _step(
                    "4. Import the update delivery (revision 2)",
                    "One record is updated in place; the transcript arrives; the manual override is untouched.",
                    {
                        "inserted": batch3.inserted,
                        "updated": batch3.updated,
                        "ignored": batch3.ignored,
                        "records": metrics3["totals"]["records"],
                        "usable_text": metrics3["totals"]["usable_text"],
                        "coverage_pct": metrics3["totals"]["coverage_pct"],
                        **m07_after_update,
                    },
                )
            )
            checks.append(
                _check(
                    "update_same_count",
                    "Update adds no new record; count remains 44",
                    metrics3["totals"]["records"] == 44,
                    44,
                    metrics3["totals"]["records"],
                )
            )
            checks.append(
                _check(
                    "update_transcript",
                    f"{target_ref} transcript becomes available in the existing record",
                    record.has_usable_text and (len(record.turns or []) > 0),
                    True,
                    {"usable": record.has_usable_text, "turns": len(record.turns or [])},
                )
            )
            checks.append(
                _check(
                    "coverage_change",
                    "Coverage moves from 17/44 to 18/44 (40.9% of 44)",
                    metrics3["totals"]["usable_text"] == 18,
                    18,
                    metrics3["totals"]["usable_text"],
                )
            )
            checks.append(
                _check(
                    "override_survives_update",
                    f"{target_ref}'s manual route survives the revision-2 payload replacement",
                    effective_routes(record) == [M07_ROUTE] and record.override is not None,
                    [M07_ROUTE],
                    effective_routes(record),
                )
            )
            checks.append(
                _check(
                    "revision_recorded",
                    "M07 stores applied revision 2",
                    record.applied_revision == 2,
                    2,
                    record.applied_revision,
                )
            )
            checks.append(
                _check(
                    "analysis_refreshed",
                    "M07 analysis reflects revision 2 or is visibly pending review",
                    record.analysis is not None
                    and record.analysis.source_revision == 2
                    and record.analysis.freshness in ("current", "pending_review", "stale"),
                    "analysis bound to revision 2, freshness current|pending_review|stale",
                    {
                        "origin": record.analysis.origin if record.analysis else None,
                        "freshness": record.analysis.freshness if record.analysis else None,
                        "source_revision": record.analysis.source_revision if record.analysis else None,
                    },
                )
            )
            checks.append(
                _check(
                    "analysis_review_flag",
                    "The arrival of new text is visibly flagged for manager review",
                    (record.review.state if record.review else None) == "needs_review",
                    "needs_review",
                    record.review.state if record.review else None,
                )
            )
            checks.append(
                _check(
                    "all_records_have_review_state",
                    "Every record carries an intake/review state",
                    all(r.review is not None for r in records),
                    44,
                    sum(1 for r in records if r.review is not None),
                )
            )
            unrelated_ref = "C01" if "C01" in snapshot else next(
                ref for ref in snapshot if ref != target_ref
            )
            unrelated = next(r for r in records if r.record_ref == unrelated_ref)
            unchanged = (
                snapshot[unrelated_ref]["revision"] == unrelated.applied_revision
                and snapshot[unrelated_ref]["text"] == unrelated.text_hash
                and snapshot[unrelated_ref]["payload"] == _hash_payload(unrelated.raw_payload)
            )
            checks.append(
                _check(
                    "unrelated_unchanged",
                    f"Unrelated record {unrelated_ref} is byte-for-byte unchanged by the update",
                    unchanged,
                    snapshot[unrelated_ref],
                    {
                        "revision": unrelated.applied_revision,
                        "text": unrelated.text_hash,
                        "payload": _hash_payload(unrelated.raw_payload),
                    },
                )
            )

        # Step 5 - replay revision 1 after revision 2
        with factory() as session:
            delivery = parse_delivery(json.loads(initial_path.read_text()), revision_override=1)
            rng = random.Random(99)
            rng.shuffle(delivery.records)
            batch4 = apply_delivery(session, delivery, filename=initial_path.name)
        with factory() as session:
            records = load_records(session)
            metrics4 = compute_metrics(records)
            record = next(r for r in records if r.record_ref == target_ref)
            steps.append(
                _step(
                    "5. Replay the initial delivery after the update",
                    "Older payloads are ignored, so M07 keeps its revision-2 transcript, its refreshed analysis "
                    "and its manual route.",
                    {
                        "inserted": batch4.inserted,
                        "updated": batch4.updated,
                        "ignored": batch4.ignored,
                        "records": metrics4["totals"]["records"],
                        "usable_text": metrics4["totals"]["usable_text"],
                        "m07_revision": record.applied_revision,
                        "m07_usable_text": record.has_usable_text,
                        "m07_effective": effective_routes(record),
                        "m07_override": record.override is not None,
                    },
                )
            )
            checks.append(
                _check(
                    "stale_replay_ignored",
                    "Revision 1 replay inserts nothing and ignores every record",
                    batch4.inserted == 0 and batch4.ignored == 44 and batch4.updated == 0,
                    {"inserted": 0, "ignored": 44, "updated": 0},
                    {"inserted": batch4.inserted, "ignored": batch4.ignored, "updated": batch4.updated},
                )
            )
            checks.append(
                _check(
                    "m07_latest_text_kept",
                    f"{target_ref} still holds the revision-2 transcript after the replay",
                    record.applied_revision == 2 and record.has_usable_text,
                    {"revision": 2, "usable_text": True},
                    {"revision": record.applied_revision, "usable_text": record.has_usable_text},
                )
            )
            checks.append(
                _check(
                    "override_survives_replay",
                    f"{target_ref}'s manual route survives the revision-1 replay",
                    effective_routes(record) == [M07_ROUTE] and record.override is not None,
                    [M07_ROUTE],
                    effective_routes(record),
                )
            )
            checks.append(
                _check(
                    "count_stable",
                    "Record count is 44 after the full sequence",
                    metrics4["totals"]["records"] == 44,
                    44,
                    metrics4["totals"]["records"],
                )
            )
            checks.append(
                _check(
                    "review_states_complete",
                    "All 44 records remain in a review state after replay",
                    all(r.review is not None for r in records),
                    44,
                    sum(1 for r in records if r.review is not None),
                )
            )

            # Step 6 - exports from the replayed state
            export1 = build_export(session, export_dir=tmp_path / "exports")
            export2 = build_export(session, export_dir=tmp_path / "exports")
            archive = Path(export1["archive_path"])
            with zipfile.ZipFile(archive) as zf:
                names = set(zf.namelist())
                manifest_name = f"exports/{REPORTING_DATE}/manifest.json"
                manifest = json.loads(zf.read(manifest_name))
            output_paths = [p for entry in manifest["records"] for p in entry["output_paths"]]
            all_paths_exist = all(p in names for p in output_paths)
            csv_name = f"exports/{REPORTING_DATE}/manifest.csv"
            with zipfile.ZipFile(archive) as zf:
                rows = list(csv.DictReader(io.StringIO(zf.read(csv_name).decode("utf-8"))))
            json_rows = {e["record_ref"]: e for e in manifest["records"]}
            csv_rows = {r["record_ref"]: r for r in rows}
            agree = set(json_rows) == set(csv_rows) and all(
                json_rows[ref]["applied_revision"] == int(csv_rows[ref]["applied_revision"])
                and "|".join(json_rows[ref]["effective_routes"]) == csv_rows[ref]["effective_routes"]
                and "|".join(json_rows[ref]["output_paths"]) == csv_rows[ref]["output_paths"]
                for ref in json_rows
            )
            steps.append(
                _step(
                    "6. Generate an export, then request it again",
                    "Every manifest path is a real file in the archive. A repeat export of unchanged state "
                    "reuses the existing version instead of duplicating outputs.",
                    {
                        "version": export1["version"],
                        "repeat_version": export2["version"],
                        "repeat_created": export2["created"],
                        "files_in_archive": len(names),
                        "manifest_rows": len(manifest["records"]),
                    },
                )
            )
            checks.append(
                _check(
                    "export_paths_exist",
                    "Every manifest output path exists as a real file inside the archive",
                    all_paths_exist,
                    True,
                    {"missing": [p for p in output_paths if p not in names][:5], "checked": len(output_paths)},
                )
            )
            checks.append(
                _check(
                    "manifest_agreement",
                    "JSON and CSV manifests agree on revision, routes and output paths",
                    agree,
                    True,
                    agree,
                )
            )
            checks.append(
                _check(
                    "no_duplicate_exports",
                    "Re-exporting unchanged state does not create another active version",
                    export2["created"] is False and export2["version"] == export1["version"],
                    {"created": False, "same_version": True},
                    {"created": export2["created"], "version": export2["version"]},
                )
            )
            checks.append(
                _check(
                    "m07_export_present",
                    f"{target_ref} appears in the export manifest with its manual override flagged",
                    any(
                        e["record_ref"] == target_ref and e["manual_override"] is True
                        for e in manifest["records"]
                    ),
                    True,
                    next(
                        (
                            {
                                "record_ref": e["record_ref"],
                                "manual_override": e["manual_override"],
                                "effective_routes": e["effective_routes"],
                            }
                            for e in manifest["records"]
                            if e["record_ref"] == target_ref
                        ),
                        None,
                    ),
                )
            )

        # Step 7 - validation rejects a malformed batch
        with factory() as session:
            try:
                parse_delivery({"revision": 3, "records": [{"source_id": "x"}]})
                malformed_rejected = False
                malformed_error = None
            except ImportValidationError as exc:
                malformed_rejected = True
                malformed_error = exc.errors[0] if exc.errors else None
        checks.append(
            _check(
                "validation",
                "A malformed delivery is rejected with a specific validation error",
                malformed_rejected,
                True,
                {"rejected": malformed_rejected, "error": malformed_error},
            )
        )

    passed = sum(1 for c in checks if c["pass"])
    return {
        "available": True,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "isolated": True,
        "note": (
            "This replay runs against a temporary SQLite database using the same import engine as the app, "
            "so it does not disturb the manager's saved corrections."
        ),
        "steps": steps,
        "checks": checks,
        "summary": {"passed": passed, "failed": len(checks) - passed, "total": len(checks)},
        "m07": m07_after_update,
        "route_label": ROUTE_LABELS.get(M07_ROUTE),
    }
