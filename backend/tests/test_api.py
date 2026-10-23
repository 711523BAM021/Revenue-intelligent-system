from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, data_dir, monkeypatch):
    import app.db as db
    import app.api as api
    import app.exports as exports_module

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api.db")
    monkeypatch.setattr(api, "DATA_DIR", data_dir)
    monkeypatch.setattr(exports_module, "EXPORT_DIR", tmp_path / "exports")
    db.reset_engine_state()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    db.reset_engine_state()


def test_meta_and_import_flow(client):
    meta = client.get("/api/meta").json()
    assert meta["reporting_date"] == "2026-08-21"
    assert len(meta["routes"]) >= 7

    response = client.post("/api/imports", json={"dataset": "initial", "shuffle": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["batch"]["inserted"] == 5
    assert body["metrics"]["records"] == 5

    repeat = client.post("/api/imports", json={"dataset": "initial"})
    assert repeat.json()["batch"]["ignored"] == 5

    records = client.get("/api/records").json()
    assert records["total"] == 5
    filtered = client.get("/api/records", params={"source_type": "call"}).json()
    assert filtered["total"] == 3
    no_text = client.get("/api/records", params={"text": "missing"}).json()
    assert no_text["total"] == 2


def test_record_detail_override_and_review(client):
    client.post("/api/imports", json={"dataset": "initial"})
    detail = client.get("/api/records/meeting/meeting-2001").json()
    assert detail["record_ref"] == "TM1"
    assert detail["turns"] and detail["turns"][0]["turn"] == 1
    assert detail["analysis"]["origin"] == "rules_derived"

    override = client.patch(
        "/api/records/meeting/meeting-2001/override",
        json={"routes": ["customer_success", "sales_coaching"], "reason": "Manager confirmed a support issue."},
    )
    assert override.status_code == 200
    body = override.json()
    assert set(body["effective_routes"]) == {"customer_success", "sales_coaching"}
    assert body["manual_override"] is True
    assert body["suggested_routes"] != body["effective_routes"]

    client.post("/api/imports", json={"dataset": "update"})
    replay = client.post("/api/imports", json={"dataset": "initial"})
    assert replay.status_code == 200
    after = client.get("/api/records/meeting/meeting-2001").json()
    assert after["manual_override"] is True
    assert set(after["effective_routes"]) == {"customer_success", "sales_coaching"}
    assert after["override"]["reason"].startswith("Manager confirmed")

    reset = client.delete("/api/records/meeting/meeting-2001/override")
    assert reset.status_code == 200
    assert reset.json()["manual_override"] is False
    assert reset.json()["effective_routes"] == reset.json()["suggested_routes"]

    reviewed = client.patch(
        "/api/records/meeting/meeting-2001/review",
        json={"state": "reviewed", "note": "Checked."},
    )
    assert reviewed.json()["review_state"] == "reviewed"


def test_late_transcript_via_update_endpoint(client):
    client.post("/api/imports", json={"dataset": "initial"})
    before = client.get("/api/records/meeting/meeting-2002").json()
    assert before["has_usable_text"] is False
    assert before["review_state"] == "awaiting_text"

    update = client.post("/api/imports", json={"dataset": "update"}).json()
    assert update["batch"]["updated"] == 2
    after = client.get("/api/records/meeting/meeting-2002").json()
    assert after["has_usable_text"] is True
    assert after["applied_revision"] == 2
    assert after["review_state"] == "needs_review"


def test_metrics_and_brief_endpoints(client):
    client.post("/api/imports", json={"dataset": "initial"})
    metrics = client.get("/api/metrics", params={"source_type": "meeting"}).json()
    assert metrics["totals"]["records"] == 2
    assert metrics["totals"]["coverage_pct"] == 50.0
    assert metrics["totals"]["coverage_denominator"] == 2

    brief = client.get("/api/brief").json()
    assert brief["brief"]["date"] == "2026-08-21"
    assert brief["findings"] and brief["rejected_decision"]
    assert brief["metrics"]["totals"]["records"] == 5


def test_export_downloads(client):
    client.post("/api/imports", json={"dataset": "initial"})
    created = client.post("/api/exports")
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["created"] is True

    archive = client.get("/api/exports/current/archive.zip")
    assert archive.status_code == 200
    assert archive.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zf:
        names = zf.namelist()
        assert "exports/2026-08-21/manifest.json" in names
        assert "exports/2026-08-21/manifest.csv" in names
        manifest = json.loads(zf.read("exports/2026-08-21/manifest.json"))
        assert len(manifest["records"]) == 5
        for entry in manifest["records"]:
            for path in entry["output_paths"]:
                assert path in names

    manifest_json = client.get("/api/exports/current/manifest.json")
    assert manifest_json.status_code == 200
    assert len(manifest_json.json()["records"]) == 5

    manifest_csv = client.get("/api/exports/current/manifest.csv")
    assert manifest_csv.status_code == 200
    assert manifest_csv.text.splitlines()[0].startswith("source_type,source_id,record_ref")

    again = client.post("/api/exports").json()
    assert again["created"] is False


def test_quality_and_replay_endpoints(client):
    client.post("/api/imports", json={"dataset": "initial"})
    quality = client.get("/api/quality").json()
    assert quality["counts"]["records"] == 5
    assert quality["counts"]["no_usable_text"] == 2
    assert quality["lists"]["no_usable_text"] == ["T02", "TM2"]

    replay = client.post("/api/replay")
    assert replay.status_code == 200
    body = replay.json()
    assert body["available"] is True
    assert body["checks"]
    assert body["summary"]["total"] == len(body["checks"])


def test_missing_dataset_returns_actionable_error(client, monkeypatch, tmp_path):
    import app.api as api

    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "empty")
    response = client.post("/api/imports", json={"dataset": "initial"})
    assert response.status_code == 409
    assert "not found" in response.json()["detail"]
