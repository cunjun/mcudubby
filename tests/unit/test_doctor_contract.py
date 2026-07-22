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


def test_doctor_does_not_warn_about_probe_rs_when_pyocd_is_selected(monkeypatch) -> None:
    monkeypatch.setattr(
        "McuBuddy.doctor._check_probes",
        lambda config: {
            "name": "probe-discovery",
            "status": "ok",
            "summary": "Found one probe.",
            "probes": [{}],
        },
    )
    monkeypatch.setattr(
        "McuBuddy.doctor._check_skill_installation",
        lambda: {"name": "mcubug-skill", "status": "ok", "summary": "installed"},
    )

    report = build_doctor_report(RuntimeConfig())

    sidecar = next(check for check in report["checks"] if check["name"] == "probe-rs-sidecar")
    assert sidecar["status"] == "ok"
    assert sidecar["required"] is False


def test_doctor_reports_source_and_installed_version_mismatch(monkeypatch) -> None:
    monkeypatch.setattr("McuBuddy.doctor.__version__", "0.5.1")
    monkeypatch.setattr("McuBuddy.doctor._read_source_version", lambda: "0.5.2")
    monkeypatch.setattr(
        "McuBuddy.doctor._check_probes",
        lambda config: {
            "name": "probe-discovery",
            "status": "ok",
            "summary": "Found one probe.",
            "probes": [{}],
        },
    )

    report = build_doctor_report(RuntimeConfig())

    version = next(check for check in report["checks"] if check["name"] == "version")
    assert version == {
        "name": "version",
        "status": "warning",
        "summary": "Installed McuBuddy 0.5.1 differs from source tree 0.5.2.",
        "installed_version": "0.5.1",
        "source_version": "0.5.2",
        "recommended_action": "Reinstall or synchronize the project environment.",
    }
    assert report["status"] == "warning"
