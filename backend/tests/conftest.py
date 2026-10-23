from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.db import session_factory_for

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _call(record_id: str, ref: str, *, rep: str | None, transcript: str | None, connected=True, outcome="connected"):
    return {
        "record_ref": ref,
        "source_type": "call",
        "source_id": record_id,
        "payload": {
            "id": record_id,
            "rep_name": rep,
            "rep_email": f"{ref.lower()}@example.test" if rep else None,
            "started_at": "2026-08-21T10:00:00Z",
            "duration_seconds": 120,
            "direction": "outbound",
            "is_connected": connected,
            "is_conversation": bool(transcript),
            "observed_outcome": outcome,
            "classification_status": "completed",
            "transcript": transcript,
        },
        "transcript_payload": None,
    }


def _meeting(record_id: str, ref: str, *, organiser: str | None, turns: list[dict], has_transcript=True, reason=None):
    return {
        "record_ref": ref,
        "source_type": "meeting",
        "source_id": record_id,
        "payload": {
            "id": record_id,
            "title": f"{ref} discussion",
            "starts_at": "2026-08-21T11:00:00Z",
            "ends_at": "2026-08-21T11:30:00Z",
            "duration_seconds": 1800,
            "provider": "example",
            "organizer_email": organiser,
            "attendee_count": 3,
            "recording_status": "recorded" if has_transcript else "not_scheduled",
            "has_transcript": has_transcript,
            "has_video": False,
            "redacted": True,
        },
        "transcript_payload": {
            "meeting_id": record_id,
            "turns": turns,
            "unavailable_reason": reason,
        },
    }


def build_initial() -> dict:
    return {
        "batch_id": "fixture-initial",
        "revision": 1,
        "exported_at": "2026-08-22T00:00:00Z",
        "records": [
            _call(
                "call-1001",
                "T01",
                rep="Rep One",
                transcript=(
                    "Hello, this is a cold call about expense software. We already have a tool. "
                    "Could you send me a proposal and call me back on Monday?"
                ),
            ),
            _call("call-1002", "T02", rep="Rep Two", transcript=None, connected=None, outcome=None),
            _call("call-1003", "T03", rep=None, transcript="We are not interested, thank you.", connected=False, outcome="not_interested"),
            _meeting(
                "meeting-2001",
                "TM1",
                organiser="org1@example.test",
                turns=[
                    {"speaker": "Customer A", "starts_at_seconds": 10, "timecode": "00:00:10", "text": "The export button does not work."},
                    {"speaker": "Team member A", "starts_at_seconds": 30, "timecode": "00:00:30", "text": "I will report it and come back to you."},
                ],
            ),
            _meeting(
                "meeting-2002",
                "TM2",
                organiser=None,
                turns=[],
                has_transcript=True,
                reason="No speech detected in the recording.",
            ),
        ],
    }


def build_update() -> dict:
    """Revision 2: TM2 gains turns, T01's payload replaces fields (including nulls)."""
    return {
        "batch_id": "fixture-update",
        "revision": 2,
        "exported_at": "2026-08-22T01:00:00Z",
        "records": [
            _meeting(
                "meeting-2002",
                "TM2",
                organiser="org2@example.test",
                turns=[
                    {"speaker": "Customer A", "starts_at_seconds": 5, "timecode": "00:00:05", "text": "The payment amount is wrong."},
                    {"speaker": "Team member A", "starts_at_seconds": 20, "timecode": "00:00:20", "text": "I will check it today."},
                ],
            ),
            {
                "record_ref": "T01",
                "source_type": "call",
                "source_id": "call-1001",
                "payload": {
                    "id": "call-1001",
                    "rep_name": None,
                    "rep_email": None,
                    "started_at": "2026-08-21T10:00:00Z",
                    "duration_seconds": 130,
                    "direction": "outbound",
                    "is_connected": True,
                    "is_conversation": True,
                    "observed_outcome": None,
                    "classification_status": "completed",
                    "transcript": "A revised transcript with different wording about pricing.",
                },
                "transcript_payload": None,
            },
        ],
    }


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    (d / "01_initial.json").write_text(json.dumps(build_initial()), encoding="utf-8")
    (d / "02_update.json").write_text(json.dumps(build_update()), encoding="utf-8")
    return d


@pytest.fixture()
def session_factory(tmp_path: Path):
    return session_factory_for(tmp_path / "test.db")
