from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .backends.probe.sidecar_client import resolve_sidecar_path
from .config import RuntimeConfig, config_for_display
from .session import SessionState, create_probe_backend


def build_doctor_report(config: RuntimeConfig) -> dict[str, Any]:
    checks = [
        _check_python(),
        _check_import("mcp", "MCP package"),
        _check_import("pyocd", "pyOCD"),
        _check_import("pylink", "J-Link Python package", optional=True),
        _check_sidecar(config),
        _check_config(config),
        _check_skill_installation(),
        _check_probes(config),
    ]
    status = _overall_status(checks)
    return {
        "status": status,
        "summary": _summary(status),
        "version": __version__,
        "checks": checks,
        "config": config_for_display(config),
    }


def _overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "error" for check in checks):
        return "error"
    if any(check["status"] == "warning" for check in checks):
        return "warning"
    return "ok"


def _summary(status: str) -> str:
    if status == "ok":
        return "McuBuddy doctor found the runtime ready."
    if status == "warning":
        return "McuBuddy doctor found warnings; review checks before hardware debugging."
    return "McuBuddy doctor found errors that should be fixed before use."


def _check_python() -> dict[str, Any]:
    version = ".".join(str(part) for part in sys.version_info[:3])
    status = "ok" if sys.version_info >= (3, 10) else "error"
    return {
        "name": "python",
        "status": status,
        "summary": f"Python {version}",
        "version": version,
    }


def _check_import(module_name: str, label: str, optional: bool = False) -> dict[str, Any]:
    found = importlib.util.find_spec(module_name) is not None
    status = "ok" if found else ("warning" if optional else "error")
    summary = f"{label} is available." if found else f"{label} is not installed."
    return {"name": module_name, "status": status, "summary": summary, "optional": optional}


def _check_sidecar(config: RuntimeConfig) -> dict[str, Any]:
    try:
        path = resolve_sidecar_path(config.probe.probe_rs_sidecar_path)
    except Exception as exc:
        return {
            "name": "probe-rs-sidecar",
            "status": "warning",
            "summary": str(exc),
        }
    return {
        "name": "probe-rs-sidecar",
        "status": "ok",
        "summary": f"probe-rs sidecar found at {path}.",
        "path": path,
    }


def _check_config(config: RuntimeConfig) -> dict[str, Any]:
    return {
        "name": "config",
        "status": "ok",
        "summary": "Runtime configuration is valid.",
        "tool_profile": config.server.tool_profile,
    }


def _check_skill_installation() -> dict[str, Any]:
    skill_path = Path.home() / ".codex" / "skills" / "mcubug" / "SKILL.md"
    if skill_path.is_file():
        return {
            "name": "mcubug-skill",
            "status": "ok",
            "summary": f"mcubug skill is installed at {skill_path}.",
            "path": str(skill_path),
        }
    return {
        "name": "mcubug-skill",
        "status": "warning",
        "summary": "mcubug skill is not installed in the default Codex skill directory.",
        "path": str(skill_path),
    }


def _check_probes(config: RuntimeConfig) -> dict[str, Any]:
    try:
        session = SessionState()
        session.config = config
        session.probe = create_probe_backend(
            config.probe.backend,
            jlink_dll_path=config.probe.jlink_dll_path,
            probe_rs_sidecar_path=config.probe.probe_rs_sidecar_path,
        )
        probes = session.probe.enumerate_probes()
    except Exception as exc:
        return {
            "name": "probe-discovery",
            "status": "warning",
            "summary": f"Probe discovery failed: {exc}",
        }
    return {
        "name": "probe-discovery",
        "status": "ok" if probes else "warning",
        "summary": f"Found {len(probes)} connected probe(s)."
        if probes
        else "No probes detected. Check USB connection and driver installation.",
        "probes": probes,
    }
