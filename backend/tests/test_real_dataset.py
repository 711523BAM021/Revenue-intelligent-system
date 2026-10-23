"""Contract tests against the supplied deliveries.

These are skipped (not silently passed) when the assessment files are absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import DATA_DIR
from app.ingest import apply_delivery, parse_delivery
from app.metrics import compute_metrics, load_records

INITIAL = DATA_DIR / "01_initial.json"
UPDATE = DATA_DIR / "02_update.json"

pytestmark = pytest.mark.skipif(
    not (INITIAL.exists() and UPDATE.exists()),
    reason="supplied 01_initial.json / 02_update.json are not present in data/",
)


def _import(session, path: Path, revision: int):
    return apply_delivery(
        session, parse_delivery(json.loads(path.read_text()), revision_override=revision), filename=path.name
    )


def test_full_replay_contract(session_factory):
    from app.replay import run_replay

    result = run_replay(DATA_DIR)
    assert result["available"] is True
    failures = [c for c in result["checks"] if not c["pass"]]
    assert not failures, failures
    assert result["summary"]["passed"] == result["summary"]["total"]


def test_initial_state_counts(session_factory):
    with session_factory() as session:
        _import(session, INITIAL, 1)
        metrics = compute_metrics(load_records(session))
        assert metrics["totals"]["records"] == 44
        assert metrics["totals"]["calls"] == 30
        assert metrics["totals"]["meetings"] == 14
        assert metrics["totals"]["usable_text"] == 17
        assert metrics["totals"]["coverage_denominator"] == 44
        # Every record has an intake/review state, including the 27 without text.
        assert all(r.review is not None for r in load_records(session))
        assert metrics["totals"]["awaiting_text"] == 27


def test_update_adds_m07_text(session_factory):
    with session_factory() as session:
        _import(session, INITIAL, 1)
        _import(session, UPDATE, 2)
        records = load_records(session)
        metrics = compute_metrics(records)
        assert metrics["totals"]["records"] == 44
        assert metrics["totals"]["usable_text"] == 18
        assert metrics["totals"]["coverage_pct"] == 40.9
        m07 = next(r for r in records if r.record_ref == "M07")
        assert m07.applied_revision == 2
        assert m07.has_usable_text
        assert m07.analysis is not None
        assert m07.analysis.source_revision == 2
        assert m07.review.state == "needs_review"


def test_corpus_evidence_matches_source(session_factory):
    """Every quoted finding must appear in the supplied text at the cited location."""
    from app.corpus import all_analyses

    with session_factory() as session:
        _import(session, INITIAL, 1)
        _import(session, UPDATE, 2)
        by_key = {(r.source_type, r.source_id): r for r in load_records(session)}
        problems = []
        for entry in all_analyses():
            record = by_key.get((entry["source_type"], entry["source_id"]))
            assert record is not None, f"corpus entry {entry['record_ref']} has no source record"
            for evidence in entry["analysis"].get("evidence", []):
                quote = evidence.get("quote", "")
                if evidence.get("kind") == "turn":
                    turn = next(
                        (t for t in record.turns or [] if t["turn"] == evidence["turn"]), None
                    )
                    if turn is None or quote not in (turn["text"] or ""):
                        problems.append((entry["record_ref"], evidence))
                else:
                    if quote not in (record.transcript_text or ""):
                        problems.append((entry["record_ref"], evidence))
        assert not problems, problems


def test_corpus_covers_all_eighteen(session_factory):
    from app.corpus import all_analyses

    with session_factory() as session:
        _import(session, INITIAL, 1)
        _import(session, UPDATE, 2)
        records = load_records(session)
        usable = [r for r in records if r.has_usable_text]
        analysed = {(r.source_type, r.source_id) for r in records if r.analysis}
        assert len(analysed) == 18
        refs = {next(r.record_ref for r in usable if (r.source_type, r.source_id) == key) for key in analysed}
        assert refs == {f"C{i:02d}" for i in range(1, 11)} | {"M01", "M02", "M03", "M04", "M06", "M07", "M09", "M10"}
