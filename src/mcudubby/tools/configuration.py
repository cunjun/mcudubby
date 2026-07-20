from __future__ import annotations

from ..backends.probe.base import ProbeCapability, probe_supports
from ..chip_matcher import match_chip_name as _match_chip_name
from ..chip_matcher import normalize_backend_name as _normalize_backend_name
from ..config import ConnectAttempt, connect_attempts_to_dicts, get_builtin_profiles
from ..device_patch_manager import list_supported_targets as _list_supported_targets
from ..device_patch_manager import resolve_device_patch as _resolve_device_patch
from ..session import SessionState, create_probe_backend


def get_runtime_config(session: SessionState) -> dict:
    return {
        "status": "ok",
        "summary": "Loaded current McuBubby runtime configuration.",
        "config": session.config.model_dump(),
    }


def list_demo_profiles() -> dict:
    profiles = get_builtin_profiles()
    return {
        "status": "ok",
        "summary": f"Found {len(profiles)} built-in demo profile(s).",
        "profiles": {name: profile.model_dump() for name, profile in profiles.items()},
    }


def load_demo_profile(session: SessionState, profile_name: str) -> dict:
    profiles = get_builtin_profiles()
    if profile_name not in profiles:
        return {
            "status": "error",
            "summary": f"Unknown demo profile: {profile_name}.",
            "available_profiles": sorted(profiles.keys()),
        }

    profile = profiles[profile_name]
    session.config.apply_profile(profile)
    return {
        "status": "ok",
        "summary": f"Loaded demo profile {profile_name}.",
        "config": session.config.model_dump(),
    }


def configure_probe(
    session: SessionState,
    target: str | None = None,
    unique_id: str | None = None,
    backend: str | None = None,
    jlink_dll_path: str | None = None,
    probe_rs_sidecar_path: str | None = None,
    pack_path: str | None = None,
    pack_paths: list[str] | None = None,
    connect_attempts: list[dict[str, object]] | None = None,
) -> dict:
    """Set probe connection parameters (target chip name and optional probe serial)."""
    requested_backend = backend or session.config.probe.backend
    next_backend = _normalize_backend_name(requested_backend)
    if next_backend is None:
        return {
            "status": "error",
            "summary": f"Unknown probe backend: {requested_backend}",
            "supported_backends": ["jlink", "probe-rs", "pyocd"],
        }

    next_config = session.config.probe.model_copy(deep=True)
    next_config.backend = next_backend
    if unique_id is not None:
        next_config.unique_id = unique_id
    if jlink_dll_path is not None:
        next_config.jlink_dll_path = jlink_dll_path
    if probe_rs_sidecar_path is not None:
        next_config.probe_rs_sidecar_path = probe_rs_sidecar_path
    if pack_paths is not None:
        next_config.pack_paths = list(pack_paths)
    if pack_path is not None and pack_path not in next_config.pack_paths:
        next_config.pack_paths.append(pack_path)
    if connect_attempts is not None:
        try:
            next_config.connect_attempts = [
                ConnectAttempt.model_validate(attempt) for attempt in connect_attempts
            ]
        except ValueError as exc:
            return {
                "status": "error",
                "summary": f"Invalid probe connection attempt: {exc}",
            }

    matched_target = None
    match_result = None
    patch_result = None
    if target is not None:
        match_result = _match_chip_name(target, backend=next_backend)
        matched_target = match_result["matched_target"]
        next_config.target = matched_target
        patch_result = _resolve_device_patch(target, backend=next_backend)

    recreate_probe = False
    if backend is not None and next_backend != session.config.probe.backend:
        recreate_probe = True
    if next_backend == "jlink" and jlink_dll_path is not None:
        recreate_probe = True
    if next_backend == "probe-rs" and probe_rs_sidecar_path is not None:
        recreate_probe = True

    candidate_probe = session.probe
    if recreate_probe:
        try:
            candidate_probe = create_probe_backend(
                next_backend,
                jlink_dll_path=next_config.jlink_dll_path,
                probe_rs_sidecar_path=next_config.probe_rs_sidecar_path,
            )
        except ValueError as exc:
            return {
                "status": "error",
                "summary": str(exc),
            }

    try:
        if probe_supports(candidate_probe, ProbeCapability.PACK_PATHS):
            candidate_probe.set_pack_paths(next_config.pack_paths)
        connect_hints = patch_result["connect_hints"] if patch_result is not None else None
        if next_config.connect_attempts:
            connect_hints = {
                "attempts": connect_attempts_to_dicts(next_config.connect_attempts)
            }
        if connect_hints is not None and probe_supports(
            candidate_probe, ProbeCapability.CONNECT_HINTS
        ):
            candidate_probe.set_connect_hints(connect_hints)
    except Exception as exc:
        if recreate_probe:
            try:
                candidate_probe.disconnect()
            except Exception:
                pass
        return {
            "status": "error",
            "summary": f"Could not prepare the probe backend: {exc}",
        }

    if recreate_probe:
        try:
            disconnect_result = session.probe.disconnect()
            if disconnect_result.get("status") == "error":
                raise RuntimeError(disconnect_result.get("summary", "disconnect failed"))
        except Exception as exc:
            try:
                candidate_probe.disconnect()
            except Exception:
                pass
            return {
                "status": "error",
                "summary": f"Could not disconnect the current probe backend: {exc}",
            }
        session.probe = candidate_probe

    session.config.probe = next_config
    result = {
        "status": "ok",
        "summary": "Updated probe configuration.",
        "probe": session.config.probe.model_dump(),
    }
    if target is not None:
        assert match_result is not None
        assert patch_result is not None
        result["target_match"] = match_result
        result["target_patch"] = patch_result
        if matched_target != target:
            result["summary"] = (
                f"Updated probe configuration. Matched target '{target}' to '{matched_target}'."
            )
    return result


def match_chip_name(target: str, backend: str = "pyocd") -> dict:
    return _match_chip_name(target, backend=backend)


def get_target_info(target: str, backend: str = "pyocd") -> dict:
    return _resolve_device_patch(target, backend=backend)


def list_supported_targets(backend: str | None = None) -> dict:
    return _list_supported_targets(backend=backend)


def configure_log(
    session: SessionState,
    uart_port: str | None = None,
    uart_baudrate: int | None = None,
) -> dict:
    """Set UART log channel parameters."""
    if uart_port is not None:
        session.config.log.port = uart_port
    if uart_baudrate is not None:
        session.config.log.baudrate = uart_baudrate
    return {
        "status": "ok",
        "summary": "Updated log configuration.",
        "log": session.config.log.model_dump(),
    }


def configure_elf(
    session: SessionState,
    elf_path: str,
) -> dict:
    """Set the path to the ELF/AXF file for symbol resolution."""
    session.config.elf.path = elf_path
    return {
        "status": "ok",
        "summary": f"ELF path set to {elf_path}.",
        "elf": session.config.elf.model_dump(),
    }


def configure_build(
    session: SessionState,
    uv4_path: str | None = None,
    project_path: str | None = None,
    target_name: str | None = None,
    build_log_path: str | None = None,
    flash_log_path: str | None = None,
) -> dict:
    """Set Keil UV4 build/flash parameters.

    Note: build_project and flash_firmware currently require Keil UV4.
    This tool is only needed if you use those features.
    """
    if uv4_path is not None:
        session.config.build.uv4_path = uv4_path
    if project_path is not None:
        session.config.build.project_path = project_path
    if target_name is not None:
        session.config.build.target_name = target_name
    if build_log_path is not None:
        session.config.build.build_log_path = build_log_path
    if flash_log_path is not None:
        session.config.build.flash_log_path = flash_log_path
    return {
        "status": "ok",
        "summary": "Updated Keil UV4 build configuration.",
        "build": session.config.build.model_dump(),
    }


def connect_with_config(session: SessionState) -> dict:
    target = session.config.probe.target
    uart_port = session.config.log.port
    elf_path = session.config.elf.path

    results: dict[str, dict] = {}
    missing = []
    errors: dict[str, str] = {}

    if not target:
        missing.append("probe.target")
    else:
        try:
            from .probe import connect_probe

            results["probe"] = connect_probe(
                session,
                target=target,
                unique_id=session.config.probe.unique_id,
            )
        except Exception as exc:
            errors["probe"] = str(exc)

    if not uart_port:
        missing.append("log.port")
    else:
        try:
            results["log"] = session.log.connect(
                port=uart_port,
                baudrate=session.config.log.baudrate,
            )
        except Exception as exc:
            errors["log"] = str(exc)

    if not elf_path:
        missing.append("elf.path")
    else:
        try:
            results["elf"] = session.elf.load(elf_path)
        except Exception as exc:
            errors["elf"] = str(exc)

    if missing or errors:
        status = "partial"
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if errors:
            details.append(
                "errors: " + ", ".join(f"{name}={message}" for name, message in errors.items())
            )
        summary = "Connected available configured resources; " + "; ".join(details) + "."
    else:
        status = "ok"
        summary = "Connected configured resources."
    return {
        "status": status,
        "summary": summary,
        "results": results,
        "missing": missing,
        "errors": errors,
        "config": session.config.model_dump(),
    }
