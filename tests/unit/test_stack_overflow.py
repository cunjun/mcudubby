"""Tests for diagnose_stack_overflow (Phase 3)."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock

from McuBubby.tools.phase3 import diagnose_stack_overflow

_CORTEX_M_SCS = 0xE000E000  # used by _probe_is_connected
_VTOR_ADDR = 0xE000ED08
_VTOR_VALUE = 0x08000000  # typical STM32 flash base
_INITIAL_SP = 0x20010000  # word 0 of vector table


def _make_session(memory: dict[int, int], sp: int) -> MagicMock:
    """Return a minimal session mock with the given memory map and current SP."""

    def read_memory(addr, size):
        return struct.pack("<I", memory.get(addr, 0))[:size]

    probe = MagicMock()
    probe.read_memory.side_effect = read_memory
    probe.read_core_registers.return_value = {"sp": sp, "pc": 0, "lr": 0, "xpsr": 0}

    session = MagicMock()
    session.probe = probe
    session.elf.is_loaded = False
    session.elf.resolve_symbol.side_effect = AttributeError("no ELF")
    return session


_BASE_MEMORY = {
    _CORTEX_M_SCS: 0x0,  # SCS ICTR - connectivity check
    _VTOR_ADDR: _VTOR_VALUE,
    _VTOR_VALUE: _INITIAL_SP,  # word 0 = initial SP
}


def test_normal_stack_usage():
    current_sp = 0x2000FF00
    session = _make_session(_BASE_MEMORY, sp=current_sp)
    result = diagnose_stack_overflow(session)

    assert result["status"] == "ok"
    assert result["stack_used_bytes"] == _INITIAL_SP - current_sp  # 256
    assert result["overflow_detected"] is None
    assert result["initial_sp"] == hex(_INITIAL_SP)
    assert result["current_sp"] == hex(current_sp)


def test_probe_not_connected():
    probe = MagicMock()
    probe.read_memory.side_effect = RuntimeError("no probe")

    session = MagicMock()
    session.probe = probe

    result = diagnose_stack_overflow(session)
    assert result["status"] == "error"
    assert "Probe" in result["summary"]


def test_vtor_read_failure():
    """Connectivity check passes but VTOR read fails."""

    def read_memory(addr, size):
        if addr == _CORTEX_M_SCS:
            return struct.pack("<I", 0)
        raise OSError("bus error")

    probe = MagicMock()
    probe.read_memory.side_effect = read_memory

    session = MagicMock()
    session.probe = probe

    result = diagnose_stack_overflow(session)
    assert result["status"] == "error"
    assert "vtor" in result["summary"].lower()


def test_sp_above_initial_sp_warning():
    """current SP above initial SP should emit a WARNING in evidence."""
    current_sp = 0x20010100  # above initial SP
    session = _make_session(_BASE_MEMORY, sp=current_sp)
    result = diagnose_stack_overflow(session)

    assert result["status"] == "ok"
    combined = " ".join(result["evidence"]).upper()
    assert "WARNING" in combined or "ABOVE INITIAL SP" in combined
