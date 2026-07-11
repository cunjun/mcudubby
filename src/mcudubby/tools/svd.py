"""MCP tool functions for SVD peripheral register access."""

from __future__ import annotations

from ..session import SessionState
from ..tool_safety import require_tool_confirmation


def svd_load(session: SessionState, svd_path: str) -> dict:
    """Load a CMSIS-SVD file for peripheral register interpretation."""
    return session.svd.load(svd_path)


def svd_list_peripherals(session: SessionState) -> dict:
    """List all peripherals defined in the loaded SVD."""
    return session.svd.list_peripherals()


def svd_get_registers(session: SessionState, peripheral: str) -> dict:
    """Return the register layout for a peripheral (no hardware read)."""
    return session.svd.get_peripheral_registers(peripheral)


def svd_read_peripheral(session: SessionState, peripheral: str) -> dict:
    """Read all register values for a peripheral and interpret each field.

    Requires probe to be connected and target to be halted.
    """
    if not session.svd.is_loaded:
        return {
            "status": "error",
            "summary": "No SVD file loaded. Call svd_load first.",
        }
    return session.svd.read_peripheral_state(peripheral, session.probe)


def svd_write_register(
    session: SessionState,
    peripheral: str,
    register: str,
    value: int,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("svd_write_register", confirm):
        return blocked
    if not session.svd.is_loaded:
        return {"status": "error", "summary": "No SVD file loaded. Call svd_load first."}
    return session.svd.write_register(peripheral, register, value, session.probe)


def svd_write_field(
    session: SessionState,
    peripheral: str,
    register: str,
    field: str,
    value: int,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("svd_write_field", confirm):
        return blocked
    if not session.svd.is_loaded:
        return {"status": "error", "summary": "No SVD file loaded. Call svd_load first."}
    return session.svd.write_field(peripheral, register, field, value, session.probe)
