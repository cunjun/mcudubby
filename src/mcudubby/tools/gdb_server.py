from __future__ import annotations

from pathlib import Path

from ..session import SessionState


def start_gdb_server(
    session: SessionState,
    port: int = 3333,
    telnet_port: int = 4444,
    probe_server_port: int = 5555,
    allow_remote: bool = False,
    confirm_remote: bool = False,
    persist: bool = False,
    target: str | None = None,
    unique_id: str | None = None,
    elf_path: str | None = None,
) -> dict:
    if allow_remote and not confirm_remote:
        return {
            "status": "error",
            "summary": (
                "Remote GDB binding exposes the debug server beyond localhost and requires "
                "explicit confirmation. Retry with confirm_remote=true."
            ),
            "safety": {
                "level": "host-process",
                "summary": "Exposes an unauthenticated debug server to remote network clients.",
                "requires_confirmation": True,
            },
        }

    resolved_target = target or session.config.probe.target
    resolved_unique_id = unique_id if unique_id is not None else session.config.probe.unique_id
    resolved_elf_path = elf_path if elf_path is not None else session.config.elf.path

    if not resolved_target:
        return {
            "status": "error",
            "summary": "Target not configured. Pass target=... or call configure_probe first.",
        }

    cwd = None
    if resolved_elf_path:
        cwd = str(Path(resolved_elf_path).resolve().parent)

    try:
        return session.gdb_server.start(
            target=resolved_target,
            unique_id=resolved_unique_id,
            port=port,
            telnet_port=telnet_port,
            probe_server_port=probe_server_port,
            allow_remote=allow_remote,
            persist=persist,
            elf_path=resolved_elf_path,
            cwd=cwd,
        )
    except Exception as e:
        return {"status": "error", "summary": str(e)}


def stop_gdb_server(session: SessionState, timeout_seconds: float = 5.0) -> dict:
    try:
        return session.gdb_server.stop(timeout_seconds=timeout_seconds)
    except Exception as e:
        return {"status": "error", "summary": str(e)}


def get_gdb_server_status(session: SessionState) -> dict:
    try:
        status = session.gdb_server.status()
        return {
            "status": "ok",
            "summary": (
                f"GDB server is running on {status['host']}:{status['port']}."
                if status["running"]
                else "GDB server is not running."
            ),
            **status,
        }
    except Exception as e:
        return {"status": "error", "summary": str(e)}


def _resolve_jlink_gdb_server_path(exe_path: str | None = None) -> str:
    candidates = [exe_path] if exe_path else []
    candidates.extend(
        [
            r"E:\software\jlink\JLinkGDBServerCL.exe",
            r"C:\Program Files\SEGGER\JLink\JLinkGDBServerCL.exe",
            r"C:\Program Files (x86)\SEGGER\JLink\JLinkGDBServerCL.exe",
        ]
    )
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    raise FileNotFoundError(
        "JLinkGDBServerCL.exe not found. Pass exe_path=... or install SEGGER J-Link."
    )


def start_jlink_gdb_server(
    session: SessionState,
    target: str | None = None,
    serial_no: str | None = None,
    port: int = 2331,
    interface: str = "swd",
    speed: int = 4000,
    exe_path: str | None = None,
) -> dict:
    resolved_target = target or session.config.probe.target
    resolved_serial = serial_no if serial_no is not None else session.config.probe.unique_id

    if not resolved_target:
        return {
            "status": "error",
            "summary": "Target not configured. Pass target=... or call configure_probe first.",
        }

    try:
        resolved_exe_path = _resolve_jlink_gdb_server_path(exe_path)
        result = session.gdb_server.start_jlink(
            target=resolved_target,
            serial_no=resolved_serial,
            port=port,
            interface=interface,
            speed=speed,
            exe_path=resolved_exe_path,
            cwd=str(Path(resolved_exe_path).resolve().parent),
        )
        log_tail = result.get("log_tail") or []
        if (
            result.get("status") == "error"
            and resolved_serial
            and any("Could not select J-Link with specified S/N" in line for line in log_tail)
        ):
            retry = session.gdb_server.start_jlink(
                target=resolved_target,
                serial_no=None,
                port=port,
                interface=interface,
                speed=speed,
                exe_path=resolved_exe_path,
                cwd=str(Path(resolved_exe_path).resolve().parent),
            )
            if retry.get("status") == "ok":
                retry["summary"] = (
                    f"{retry['summary']} Falling back to auto-selected J-Link because "
                    f"serial {resolved_serial} was rejected by JLinkGDBServerCL."
                )
                retry["requested_serial_no"] = resolved_serial
            return retry
        return result
    except Exception as e:
        return {"status": "error", "summary": str(e)}


def get_jlink_gdb_server_status(session: SessionState) -> dict:
    try:
        status = session.gdb_server.status()
        if status.get("backend") != "jlink":
            return {
                "status": "ok",
                "summary": "J-Link GDB server is not running.",
                **status,
            }
        return {
            "status": "ok",
            "summary": (
                f"J-Link GDB server is running on {status['host']}:{status['port']}."
                if status["running"]
                else "J-Link GDB server is not running."
            ),
            **status,
        }
    except Exception as e:
        return {"status": "error", "summary": str(e)}


def stop_jlink_gdb_server(session: SessionState, timeout_seconds: float = 5.0) -> dict:
    try:
        status = session.gdb_server.status()
        if status.get("backend") != "jlink":
            return {
                "status": "ok",
                "summary": "J-Link GDB server is not running.",
                **status,
            }
        return session.gdb_server.stop(timeout_seconds=timeout_seconds)
    except Exception as e:
        return {"status": "error", "summary": str(e)}
