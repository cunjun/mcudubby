from __future__ import annotations

from ..session import SessionState
from ..tool_safety import require_tool_confirmation


def build_project(session: SessionState, timeout_seconds: int = 120) -> dict:
    return session.build.build(
        build=session.config.build,
        elf=session.config.elf,
        timeout_seconds=timeout_seconds,
    )


def flash_firmware(
    session: SessionState,
    timeout_seconds: int = 120,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("flash_firmware", confirm):
        return blocked

    disconnect_note = None
    try:
        disconnect_note = session.probe.disconnect()
    except Exception:
        disconnect_note = None

    result = session.build.flash(
        build=session.config.build,
        elf=session.config.elf,
        timeout_seconds=timeout_seconds,
    )
    if disconnect_note:
        result["probe_disconnect"] = disconnect_note
    return result
