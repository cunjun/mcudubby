from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..session import SessionState


from .phase3_common import _probe_is_connected


def diagnose_stack_overflow(session: SessionState) -> dict[str, Any]:
    """Diagnose potential stack overflow on a Cortex-M target.

    Reads VTOR (0xE000ED08) to locate the vector table, extracts the
    reset-time initial SP from word 0, and compares it with the current SP.
    If an ELF is loaded and _Min_Stack_Size is available, reports remaining
    stack space and flags a likely overflow.
    Requires probe connected and target halted.
    """
    if not _probe_is_connected(session):
        return {
            "status": "error",
            "summary": "Probe not connected. Call probe_connect or connect_with_config first.",
        }

    # Step 1: read VTOR to find vector table base
    try:
        raw = session.probe.read_memory(0xE000ED08, 4)
        vtor_value = int.from_bytes(raw, "little")
    except Exception as exc:
        return {"status": "error", "summary": f"Failed to read VTOR (0xE000ED08): {exc}"}

    vector_table_base = vtor_value & 0xFFFFFF80

    # Step 2: word 0 of the vector table = initial SP at reset
    try:
        raw = session.probe.read_memory(vector_table_base, 4)
        initial_sp = int.from_bytes(raw, "little")
    except Exception as exc:
        return {
            "status": "error",
            "summary": f"Failed to read vector table at {hex(vector_table_base)}: {exc}",
        }

    # Step 3: current SP from core registers
    try:
        regs = session.probe.read_core_registers()
        current_sp = regs["sp"]
    except Exception as exc:
        return {"status": "error", "summary": f"Failed to read core registers: {exc}"}

    stack_used_bytes = initial_sp - current_sp

    # Step 4: optional ELF stack size
    # Try GCC linker symbol first (_Min_Stack_Size: address field holds size in bytes),
    # then fall back to Keil ARM Compiler symbol (Stack_Mem: address is stack bottom, size is allocated bytes).
    stack_allocated_bytes: int | None = None
    overflow_detected: bool | None = None
    stack_bottom: int | None = None
    try:
        result = session.elf.resolve_symbol("_Min_Stack_Size")
        if isinstance(result, dict) and result.get("address") is not None:
            min_stack_size = int(result["address"], 16)
            stack_allocated_bytes = min_stack_size
            stack_bottom = initial_sp - min_stack_size
            overflow_detected = current_sp < stack_bottom
    except Exception:
        pass

    if stack_bottom is None:
        try:
            result = session.elf.resolve_symbol("Stack_Mem")
            if (
                isinstance(result, dict)
                and result.get("address") is not None
                and result.get("size")
            ):
                stack_bottom = int(result["address"], 16)
                stack_allocated_bytes = result["size"]
                overflow_detected = current_sp < stack_bottom
        except Exception:
            pass

    # Step 5: build evidence list
    evidence: list[str] = [
        f"Initial SP (from VTOR): {hex(initial_sp)}",
        f"Current SP: {hex(current_sp)}, stack used: {stack_used_bytes} bytes",
    ]
    if stack_used_bytes < 0:
        evidence.append(
            "WARNING: current SP is above initial SP -- "
            "possible VTOR mismatch or stack not yet initialized."
        )
    if overflow_detected is True:
        evidence.append(
            f"STACK OVERFLOW likely: SP {hex(current_sp)} < stack bottom {hex(stack_bottom)}"
        )
    elif overflow_detected is False:
        evidence.append(
            f"Stack OK: {stack_allocated_bytes - stack_used_bytes} bytes remaining "
            f"of {stack_allocated_bytes} allocated."
        )
    else:
        evidence.append(
            "Stack size unknown (no ELF or _Min_Stack_Size symbol not found). "
            "Cannot determine if overflow occurred."
        )

    return {
        "status": "ok",
        "summary": f"Stack analysis: SP={hex(current_sp)}, used={stack_used_bytes} bytes from top.",
        "vtor": hex(vtor_value),
        "vector_table_base": hex(vector_table_base),
        "initial_sp": hex(initial_sp),
        "current_sp": hex(current_sp),
        "stack_used_bytes": stack_used_bytes,
        "stack_allocated_bytes": stack_allocated_bytes,
        "overflow_detected": overflow_detected,
        "evidence": evidence,
    }
