"""Loads the pre-generated, human-reviewed analysis library.

The library is a build-time artifact authored against the supplied conversation
text (see README: "Pre-generated analysis"). It is loaded read-only; nothing in
this module calls a model or the network.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"


@lru_cache(maxsize=1)
def load_corpus() -> dict:
    analyses: dict[str, dict] = {}
    for name in ("calls.json", "meetings.json"):
        path = CORPUS_DIR / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for record in data.get("analyses", []):
            analyses[f"{record['source_type']}:{record['source_id']}"] = record

    editorial_path = CORPUS_DIR / "editorial.json"
    editorial = (
        json.loads(editorial_path.read_text(encoding="utf-8"))
        if editorial_path.exists()
        else {}
    )
    return {"analyses": analyses, "editorial": editorial}


def corpus_analysis(source_type: str, source_id: str) -> dict | None:
    return load_corpus()["analyses"].get(f"{source_type}:{source_id}")


def editorial() -> dict:
    return load_corpus()["editorial"]


def all_analyses() -> list[dict]:
    return list(load_corpus()["analyses"].values())
