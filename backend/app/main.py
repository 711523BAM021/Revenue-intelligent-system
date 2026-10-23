from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .config import ALLOWED_ORIGINS, ROOT_DIR
from .db import init_db

app = FastAPI(
    title="Revenue Intelligence Inbox API",
    version="1.0.0",
    description="Conversation review, evidence-backed routing and revision-aware imports.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=os.environ.get("RII_ALLOWED_ORIGIN_REGEX") or None,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


# Optional single-process deployment: serve the built React app if it exists.
DIST = ROOT_DIR / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return FileResponse(DIST / "index.html", status_code=404)
        candidate = DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
