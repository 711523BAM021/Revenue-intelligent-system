"""Runtime configuration (environment-driven, no secrets required)."""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


DATA_DIR = _env_path("RII_DATA_DIR", ROOT_DIR / "data")
DB_PATH = _env_path("RII_DB_PATH", BACKEND_DIR / "var" / "revenue_intelligence.db")
EXPORT_DIR = _env_path("RII_EXPORT_DIR", ROOT_DIR / "exports")
ARTIFACT_DIR = _env_path("RII_ARTIFACT_DIR", ROOT_DIR / "artifacts")

REPORTING_DATE = "2026-08-21"
REPORTING_TZ = "Asia/Kolkata"

DATASET_FILES = {"initial": "01_initial.json", "update": "02_update.json"}

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "RII_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,"
        "http://127.0.0.1:3000,http://localhost:4173",
    ).split(",")
    if o.strip()
]

EXPORT_BASENAME = "revenue-intelligence-export"
