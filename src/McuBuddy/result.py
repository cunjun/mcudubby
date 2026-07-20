from __future__ import annotations

from typing import Any


RESERVED_RESULT_KEYS = {"status", "summary", "evidence", "next_tools", "safety"}


def safety_info(level: str, *notes: str) -> dict[str, Any]:
    return {
        "level": level,
        "notes": [note for note in notes if note],
    }


def make_result(
    *,
    status: str,
    summary: str,
    evidence: list[dict[str, Any]] | None = None,
    next_tools: list[str] | None = None,
    safety: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": status,
        "summary": summary,
        "evidence": evidence or [],
        "next_tools": next_tools or [],
        "safety": safety or safety_info("unknown"),
    }
    if payload:
        result.update(
            {
                key: value
                for key, value in payload.items()
                if key not in RESERVED_RESULT_KEYS
            }
        )
    return result
