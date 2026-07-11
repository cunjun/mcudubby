from __future__ import annotations

from collections.abc import Callable
from importlib import metadata
import sys
from typing import Any

from ..result import make_result, safety_info
from ..session import SessionState
from .configuration import configure_elf, configure_probe, get_target_info
from .probe import connect_probe, halt_target, list_connected_probes, read_stopped_context


def doctor(session: SessionState) -> dict:
    """Run a read-only environment and configuration preflight."""
    evidence: list[dict[str, Any]] = []
    warnings: list[str] = []

    evidence.append(
        {
            "kind": "runtime",
            "result": {
                "python": sys.version.split()[0],
                "executable": sys.executable,
            },
        }
    )

    for package in _expected_packages(session.config.probe.backend):
        dependency = _package_status(package)
        evidence.append({"kind": "dependency", "result": dependency})
        if dependency["status"] != "ok":
            warnings.append(f"Missing Python package: {package}")

    probes = _capture_without_steps(lambda: list_connected_probes(session))
    evidence.append({"kind": "probe_discovery", "result": probes})
    if probes.get("status") != "ok" or not probes.get("probes"):
        warnings.append("No connected probes detected.")

    if session.config.probe.target:
        target_info = get_target_info(
            session.config.probe.target, backend=session.config.probe.backend
        )
        evidence.append({"kind": "target_info", "result": target_info})
        if target_info.get("status") != "ok":
            warnings.append(f"Target preflight failed for {session.config.probe.target}.")
    else:
        evidence.append(
            {
                "kind": "target_info",
                "result": {
                    "status": "warning",
                    "summary": "No target configured yet.",
                },
            }
        )
        warnings.append("No target configured.")

    evidence.append({"kind": "configuration", "result": session.config.model_dump()})

    status = "ok" if not warnings else "warning"
    return make_result(
        status=status,
        summary=_doctor_summary(warnings),
        evidence=evidence,
        next_tools=["first_contact", "board_smoke_test", "configure_probe"],
        safety=safety_info(
            "read-only",
            "Checks Python runtime, package availability, probe discovery, target metadata, and current config.",
            "Does not connect to the target, halt, reset, write memory, or flash.",
        ),
        payload={"warnings": warnings, "config": session.config.model_dump()},
    )


def first_contact(
    session: SessionState,
    target: str,
    backend: str = "pyocd",
    unique_id: str | None = None,
    elf_path: str | None = None,
    pack_path: str | None = None,
    pack_paths: list[str] | None = None,
    disconnect_after: bool = True,
) -> dict:
    """Run the safest first board contact flow and return suggested next tools."""
    evidence: list[dict[str, Any]] = []

    target_info = get_target_info(target, backend=backend)
    evidence.append({"kind": "target_info", "result": target_info})

    probe_config = configure_probe(
        session,
        target=target,
        backend=backend,
        unique_id=unique_id,
        pack_path=pack_path,
        pack_paths=pack_paths,
    )
    evidence.append({"kind": "probe_config", "result": probe_config})

    if elf_path:
        elf_config = configure_elf(session, elf_path)
        evidence.append({"kind": "elf_config", "result": elf_config})

    smoke = board_smoke_test(session, disconnect_after=disconnect_after)
    evidence.append({"kind": "smoke_test", "result": smoke})

    status = (
        "ok" if smoke.get("status") == "ok" and probe_config.get("status") == "ok" else "partial"
    )
    next_tools = ["read_stopped_context", "diagnose"]
    if elf_path:
        next_tools.extend(["run_to_function", "backtrace"])
    next_tools.extend(["svd_load", "svd_read_peripheral"])

    return make_result(
        status=status,
        summary=_first_contact_summary(status, target_info, smoke),
        evidence=evidence,
        next_tools=next_tools,
        safety=safety_info(
            "read-only",
            "Runs probe discovery, target preflight, configuration, connect/halt reads, and optional ELF load.",
            "Does not erase flash, program flash, write memory, or write peripheral registers.",
        ),
        payload={
            "target_info": target_info,
            "config": session.config.model_dump(),
        },
    )


def board_smoke_test(
    session: SessionState,
    target: str | None = None,
    unique_id: str | None = None,
    load_elf: bool = True,
    halt: bool = True,
    read_vectors: bool = True,
    vector_address: int = 0x08000000,
    vector_words: int = 4,
    disconnect_after: bool = False,
) -> dict:
    """Run a generic read-only hardware sanity check against the configured board."""
    steps: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    probes = _capture(
        "list_connected_probes", lambda: list_connected_probes(session), steps, errors
    )

    if load_elf and session.config.elf.path:
        _capture("elf_load", lambda: session.elf.load(session.config.elf.path), steps, errors)

    resolved_target = target or session.config.probe.target
    resolved_unique_id = unique_id or session.config.probe.unique_id
    if resolved_target:
        _capture(
            "connect_probe",
            lambda: connect_probe(session, target=resolved_target, unique_id=resolved_unique_id),
            steps,
            errors,
        )
    else:
        errors["connect_probe"] = "No target configured. Pass target or call configure_probe first."

    if halt and "connect_probe" not in errors:
        _capture("halt_target", lambda: halt_target(session), steps, errors)

    if "connect_probe" not in errors:
        _capture(
            "read_stopped_context",
            lambda: read_stopped_context(
                session,
                include_fault_registers=True,
                include_logs=False,
                resolve_symbols=True,
            ),
            steps,
            errors,
        )
        if read_vectors:
            _capture(
                "read_vector_table",
                lambda: _read_vector_table(session, vector_address, vector_words),
                steps,
                errors,
            )

    if disconnect_after:
        _capture("probe_disconnect", lambda: session.probe.disconnect(), steps, errors)

    status = "ok" if not errors else "partial"
    probe_count = len(probes.get("probes", [])) if isinstance(probes, dict) else 0
    next_tools = ["read_stopped_context", "diagnose"]
    if session.config.elf.path:
        next_tools.extend(["run_to_function", "backtrace"])
    return make_result(
        status=status,
        summary=_summarize(status, probe_count, errors),
        evidence=[{"kind": "smoke_step", "step": step["step"], "result": step} for step in steps],
        next_tools=next_tools,
        safety=safety_info(
            "read-only",
            "Connects, halts, reads CPU state, optionally reads vector table, and can disconnect.",
            "Does not write memory, registers, or flash.",
        ),
        payload={
            "steps": steps,
            "errors": errors,
            "config": session.config.model_dump(),
        },
    )


def _capture(
    name: str,
    fn: Callable[[], Any],
    steps: list[dict[str, Any]],
    errors: dict[str, str],
) -> dict:
    try:
        result = fn()
        steps.append({"step": name, "result": result})
        return result if isinstance(result, dict) else {"result": result}
    except Exception as exc:
        errors[name] = str(exc)
        steps.append({"step": name, "error": str(exc)})
        return {}


def _capture_without_steps(fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        result = fn()
        return result if isinstance(result, dict) else {"status": "ok", "result": result}
    except Exception as exc:
        return {"status": "error", "summary": str(exc)}


def _read_vector_table(session: SessionState, address: int, word_count: int) -> dict:
    raw = session.probe.read_memory(address, max(0, word_count) * 4)
    words = [int.from_bytes(raw[index : index + 4], "little") for index in range(0, len(raw), 4)]
    labels = ["initial_sp", "reset_handler", "nmi_handler", "hardfault_handler"]
    decoded = {
        labels[index] if index < len(labels) else f"word_{index}": hex(value)
        for index, value in enumerate(words)
    }
    return {
        "status": "ok",
        "summary": f"Read {len(words)} vector table word(s) at {hex(address)}.",
        "address": hex(address),
        "words": [hex(value) for value in words],
        "decoded": decoded,
    }


def _summarize(status: str, probe_count: int, errors: dict[str, str]) -> str:
    if status == "ok":
        return f"Board smoke test passed; found {probe_count} probe(s), connected, and read target state."
    return "Board smoke test completed with issues: " + ", ".join(errors.keys()) + "."


def _first_contact_summary(status: str, target_info: dict, smoke: dict) -> str:
    matched = target_info.get("matched_target") or target_info.get("target") or "target"
    if status == "ok":
        return f"First contact succeeded for {matched}; board is reachable and basic state is readable."
    return f"First contact completed with issues for {matched}: {smoke.get('summary', 'see evidence')}."


def _expected_packages(backend: str) -> list[str]:
    packages = ["mcp", "pyocd", "pyserial", "pyelftools", "cmsis-svd"]
    if backend == "jlink":
        packages.append("pylink-square")
    return packages


def _package_status(package: str) -> dict[str, Any]:
    try:
        return {
            "status": "ok",
            "package": package,
            "version": metadata.version(package),
        }
    except metadata.PackageNotFoundError:
        return {
            "status": "missing",
            "package": package,
            "install_hint": f"pip install {package}",
        }


def _doctor_summary(warnings: list[str]) -> str:
    if not warnings:
        return "mcudubby doctor found the runtime, dependencies, probe discovery path, and configuration ready for first contact."
    return "mcudubby doctor found issues: " + "; ".join(warnings) + "."
