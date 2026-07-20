from __future__ import annotations

from ...session import SessionState
from ...tool_safety import require_tool_confirmation


def erase_flash(
    session: SessionState,
    start_address: int | None = None,
    end_address: int | None = None,
    chip_erase: bool = False,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("erase_flash", confirm):
        return blocked
    try:
        return session.probe.erase_flash(
            start_address=start_address,
            end_address=end_address,
            chip_erase=chip_erase,
        )
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }


def program_flash(
    session: SessionState,
    address: int,
    data: list[int] | bytes,
    verify: bool = True,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("program_flash", confirm):
        return blocked
    try:
        payload = bytes(data) if not isinstance(data, bytes) else data
        return session.probe.program_flash(address=address, data=payload, verify=verify)
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }


def verify_flash(
    session: SessionState,
    address: int,
    data: list[int] | bytes,
) -> dict:
    try:
        payload = bytes(data) if not isinstance(data, bytes) else data
        return session.probe.verify_flash(address=address, data=payload)
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }
