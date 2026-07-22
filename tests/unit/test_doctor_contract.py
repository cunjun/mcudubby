from __future__ import annotations

from McuBuddy.config import RuntimeConfig
from McuBuddy.doctor import DOCTOR_SCHEMA_VERSION, build_doctor_report


def test_doctor_report_has_versioned_json_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        "McuBuddy.doctor._check_probes",
        lambda config: {
            "name": "probe-discovery",
            "status": "warning",
            "summary": "No probes detected.",
            "probes": [],
        },
    )

    report = build_doctor_report(RuntimeConfig())

    assert report["schema_version"] == DOCTOR_SCHEMA_VERSION
    assert report["status"] in {"ok", "warning", "error"}
    assert all(
        {"name", "status", "summary"}.issubset(check)
        and check["status"] in {"ok", "warning", "error"}
        for check in report["checks"]
    )
