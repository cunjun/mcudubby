from __future__ import annotations

import json
from importlib import resources
from typing import Any


def list_validation_records() -> dict[str, Any]:
    records = _load_records()
    return {
        "status": "ok",
        "summary": f"Loaded {len(records)} hardware validation record(s).",
        "count": len(records),
        "records": records,
    }


def _load_records() -> list[dict[str, Any]]:
    validation_dir = resources.files("mcudubby.validation")
    records: list[dict[str, Any]] = []
    for path in sorted(validation_dir.iterdir(), key=lambda item: item.name):
        if path.suffix != ".json":
            continue
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records
