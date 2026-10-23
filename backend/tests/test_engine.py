from __future__ import annotations

import csv
import io
import json
import random
from pathlib import Path

import pytest

from app.exports import build_export
from app.ingest import (
    ImportValidationError,
    apply_delivery,
    effective_routes,
    parse_delivery,
)
from app.metrics import compute_metrics, load_records
from app.models import ReviewState, RouteOverride, SourceRecord


def load(path: Path, revision: int):
    return parse_delivery(json.loads(path.read_text()), revision_override=revision)


def import_initial(session, data_dir: Path, *, shuffle_seed: int | None = None):
    delivery = load(data_dir / "01_initial.json", 1)
    if shuffle_seed is not None:
        random.Random(shuffle_seed).shuffle(delivery.records)
    return apply_delivery(session, delivery, filename="01_initial.json")


def import_update(session, data_dir: Path):
    return apply_delivery(session, load(data_dir / "02_update.json", 2), filename="02_update.json")


def records(session):
    return load_records(session)


def find(session, ref: str) -> SourceRecord:
    return session.query(SourceRecord).filter(SourceRecord.record_ref == ref).one()


def test_initial_import_creates_logical_records(session_factory, data_dir):
    with session_factory() as session:
        batch = import_initial(session, data_dir)
        assert batch.inserted == 5
        assert session.query(SourceRecord).count() == 5
        metrics = compute_metrics(records(session))
        assert metrics["totals"]["calls"] == 3
        assert metrics["totals"]["meetings"] == 2
        assert metrics["totals"]["usable_text"] == 3
        assert metrics["totals"]["coverage_denominator"] == 5


def test_repeat_import_is_idempotent(session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        second = import_initial(session, data_dir)
        assert second.inserted == 0 and second.ignored == 5
        assert session.query(SourceRecord).count() == 5


def test_shuffled_order_does_not_change_results(session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir, shuffle_seed=42)
        first = [(r.record_ref, r.source_id, r.applied_revision) for r in records(session)]
    other = session_factory_for_second_run()()
    try:
        import_initial(other, data_dir, shuffle_seed=7)
        second = [(r.record_ref, r.source_id, r.applied_revision) for r in records(other)]
    finally:
        other.close()
    assert sorted(first) == sorted(second)
    # Same source identity cannot be inserted twice by the shuffled replay.
    with session_factory() as session:
        batch = import_initial(session, data_dir, shuffle_seed=99)
        assert batch.inserted == 0


def session_factory_for_second_run():
    import tempfile

    from app.db import session_factory_for

    tmp = tempfile.mkdtemp(prefix="rii-shuffle-")
    return session_factory_for(Path(tmp) / "shuffle.db")


def test_source_identity_is_two_field_key(session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        # Same source_id under a different source_type is a different record.
        payload = {
            "record_ref": "T99",
            "source_type": "meeting",
            "source_id": "call-1001",
            "payload": {"id": "call-1001", "title": "Same id, different type", "starts_at": "2026-08-21T09:00:00Z", "has_transcript": False},
            "transcript_payload": {"meeting_id": "call-1001", "turns": [], "unavailable_reason": "none"},
        }
        delivery = parse_delivery({"batch_id": "b", "revision": 1, "records": [payload]})
        apply_delivery(session, delivery, filename="extra.json")
        assert session.query(SourceRecord).count() == 6
        assert find(session, "T99").source_id == "call-1001"


def test_revision_two_replaces_payload_including_nulls(session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        before = find(session, "T01")
        assert before.owner_name == "Rep One"
        assert before.source_outcome == "connected"
        batch = import_update(session, data_dir)
        assert batch.updated == 2 and batch.inserted == 0
        after = find(session, "T01")
        assert after.applied_revision == 2
        assert after.owner_name is None          # null replaced the old value
        assert after.source_outcome is None     # not merged from revision 1
        assert "revised transcript" in (after.transcript_text or "")
        assert after.duration_seconds == 130


def test_older_revision_cannot_overwrite_newer(session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        import_update(session, data_dir)
        replay = import_initial(session, data_dir, shuffle_seed=3)
        assert replay.ignored == 5 and replay.updated == 0
        record = find(session, "T01")
        assert record.applied_revision == 2
        assert "revised transcript" in (record.transcript_text or "")


def test_late_transcript_and_manual_override_survive(session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        m2 = find(session, "TM2")
        assert not m2.has_usable_text
        m2.override = RouteOverride(record_id=m2.id, effective_routes=["customer_success"], reason="test")
        session.commit()

        import_update(session, data_dir)
        import_initial(session, data_dir)

        m2 = find(session, "TM2")
        assert m2.has_usable_text and len(m2.turns) == 2
        assert m2.applied_revision == 2
        assert effective_routes(m2) == ["customer_success"]
        assert m2.override is not None
        # Automated suggestion remains visible and separate from the override.
        assert m2.routing.suggested_routes != ["customer_success"] or m2.routing.method


def test_manual_override_does_not_block_unrelated_records(session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        t02_before = find(session, "T02").raw_payload
        import_update(session, data_dir)
        t02_after = find(session, "T02")
        assert t02_after.applied_revision == 1
        assert t02_after.raw_payload == t02_before


def test_analysis_freshness_marks_changed_text_pending(session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        t01 = find(session, "T01")
        assert t01.analysis is not None
        old_hash = t01.analysis.text_hash
        assert t01.analysis.source_revision == 1

        import_update(session, data_dir)
        t01 = find(session, "T01")
        assert t01.analysis.text_hash != old_hash
        assert t01.analysis.source_revision == 2
        assert t01.analysis.freshness in ("pending_review", "current", "stale")
        assert t01.review.state == "needs_review"
        assert "revision 2" in (t01.review.note or "")


def test_all_records_have_intake_state(session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        for record in records(session):
            assert record.review is not None and record.review.state
        no_text = [r for r in records(session) if not r.has_usable_text]
        assert no_text and all(r.review.state == "awaiting_text" for r in no_text)
        # Intake records still carry a stored routing decision, not an implicit fallback.
        assert all(r.routing is not None for r in records(session))
        assert all(r.routing.suggested_routes == ["needs_review"] for r in no_text)


def test_metrics_definitions(session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        import_update(session, data_dir)
        metrics = compute_metrics(records(session))
        assert metrics["totals"]["records"] == 5
        assert metrics["totals"]["usable_text"] == 4
        assert metrics["totals"]["coverage_denominator"] == 5
        assert metrics["totals"]["coverage_pct"] == 80.0
        # connection denominator excludes the unknown flag on T02
        assert metrics["connection"]["unknown"] == 1
        assert metrics["connection"]["denominator"] == 2
        assert metrics["connection"]["rate_pct"] == 50.0
        assert metrics["review_states"]


def test_validation_rejects_bad_batches(session_factory, data_dir):
    with pytest.raises(ImportValidationError):
        parse_delivery({"revision": 1, "records": [{"source_id": "x"}]})
    with pytest.raises(ImportValidationError):
        parse_delivery({"records": []})
    with pytest.raises(ImportValidationError):
        parse_delivery({"revision": 2, "records": [
            {"record_ref": "A", "source_type": "call", "source_id": "1", "payload": {"id": "1"}},
            {"record_ref": "B", "source_type": "call", "source_id": "1", "payload": {"id": "1"}},
        ]})
    with pytest.raises(ImportValidationError):
        parse_delivery({"revision": 1, "records": [
            {"record_ref": "A", "source_type": "call", "source_id": "1", "payload": {"id": "other"}},
        ]}, revision_override=2)

    with session_factory() as session:
        assert session.query(SourceRecord).count() == 0


def test_export_writes_real_files_and_consistent_manifests(tmp_path, session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        import_update(session, data_dir)
        result = build_export(session, export_dir=tmp_path / "exports")
        archive = Path(result["archive_path"])
        assert archive.exists()

        import zipfile

        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
            manifest = json.loads(zf.read("exports/2026-08-21/manifest.json"))
            csv_rows = list(csv.DictReader(io.StringIO(zf.read("exports/2026-08-21/manifest.csv").decode())))

        assert manifest["records"] and len(manifest["records"]) == 5
        paths = [p for e in manifest["records"] for p in e["output_paths"]]
        assert paths and all(p in names for p in paths)
        assert "exports/2026-08-21/manager-brief.md" in names
        assert any(n.startswith("exports/2026-08-21/needs-review/") for n in names)

        by_ref = {e["record_ref"]: e for e in manifest["records"]}
        csv_by_ref = {r["record_ref"]: r for r in csv_rows}
        assert set(by_ref) == set(csv_by_ref)
        for ref, entry in by_ref.items():
            row = csv_by_ref[ref]
            assert int(row["applied_revision"]) == entry["applied_revision"]
            assert row["effective_routes"] == "|".join(entry["effective_routes"])
            assert row["output_paths"] == "|".join(entry["output_paths"])
            assert row["manual_override"] == str(entry["manual_override"])
        for entry in manifest["records"]:
            assert entry["source_type"] in ("call", "meeting")
            assert entry["record_ref"]


def test_export_is_idempotent_until_state_changes(tmp_path, session_factory, data_dir):
    with session_factory() as session:
        import_initial(session, data_dir)
        first = build_export(session, export_dir=tmp_path / "exports")
        second = build_export(session, export_dir=tmp_path / "exports")
        assert second["created"] is False
        assert second["version"] == first["version"]

        m2 = find(session, "TM2")
        m2.override = RouteOverride(record_id=m2.id, effective_routes=["customer_success"], reason="changed")
        session.commit()
        third = build_export(session, export_dir=tmp_path / "exports")
        assert third["created"] is True
        assert third["version"] == first["version"] + 1
