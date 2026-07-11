"""Tests for conditional breakpoint logic in tools/probe.py."""

from __future__ import annotations

from mcudubby.tools.probe import (
    _evaluate_condition,
    clear_all_breakpoints,
    clear_breakpoint,
    continue_target,
    continue_until,
    set_breakpoint,
    list_conditional_breakpoints,
)


# ---------------------------------------------------------------------------
# Minimal fakes
# ---------------------------------------------------------------------------


class _FakeElfNotLoaded:
    is_loaded = False

    def resolve_address(self, address):
        return {"symbol": None, "source": None}

    def resolve_symbol(self, name):
        return {"address": None, "source": None}


class _FakeElf:
    is_loaded = True

    def resolve_address(self, address):
        return {"symbol": f"sym_{hex(address)}", "source": None}

    def resolve_symbol(self, name):
        # "counter" symbol lives at 0x20000100
        if name == "counter":
            return {"address": "0x20000100", "source": None}
        return {"address": None, "source": None}


class _FakeProbeStaticRegister:
    """Probe whose read_core_registers always returns the same values."""

    def __init__(self, halt_pc: int, registers: dict):
        self._halt_pc = halt_pc
        self._registers = registers
        self._breakpoints: set[int] = set()

    def set_breakpoint(self, address):
        self._breakpoints.add(address)
        return {"status": "ok"}

    def clear_breakpoint(self, address):
        self._breakpoints.discard(address)
        return {"status": "ok"}

    def clear_all_breakpoints(self):
        self._breakpoints.clear()
        return {"status": "ok", "cleared_count": 0}

    def continue_target(self, timeout_seconds=5.0, poll_interval_seconds=0.05):
        return {"status": "ok", "stop_reason": "breakpoint_hit", "pc": hex(self._halt_pc)}

    def read_core_registers(self):
        return dict(self._registers)

    def read_memory(self, address, size):
        return b"\x00" * size


class _FakeProbeSequentialRegister:
    """Probe whose read_core_registers returns values from a sequence, cycling on the last."""

    def __init__(self, halt_pc: int, register_sequence: list[dict]):
        self._halt_pc = halt_pc
        self._sequence = register_sequence
        self._call_idx = 0
        self._breakpoints: set[int] = set()

    def set_breakpoint(self, address):
        self._breakpoints.add(address)
        return {"status": "ok"}

    def clear_breakpoint(self, address):
        self._breakpoints.discard(address)
        return {"status": "ok"}

    def clear_all_breakpoints(self):
        self._breakpoints.clear()
        return {"status": "ok", "cleared_count": 0}

    def continue_target(self, timeout_seconds=5.0, poll_interval_seconds=0.05):
        return {"status": "ok", "stop_reason": "breakpoint_hit", "pc": hex(self._halt_pc)}

    def read_core_registers(self):
        idx = min(self._call_idx, len(self._sequence) - 1)
        self._call_idx += 1
        return dict(self._sequence[idx])

    def read_memory(self, address, size):
        return b"\x00" * size


class _FakeSession:
    def __init__(self, probe, elf=None):
        self.probe = probe
        self.elf = elf or _FakeElfNotLoaded()
        self.conditional_breakpoints: dict = {}


# ---------------------------------------------------------------------------
# _evaluate_condition
# ---------------------------------------------------------------------------


def test_evaluate_condition_register_met():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234, "r0": 5})
    session = _FakeSession(probe)
    cond = {
        "condition_symbol": None,
        "condition_register": "r0",
        "condition_op": "eq",
        "condition_value": 5,
    }
    assert _evaluate_condition(session, cond) is True


def test_evaluate_condition_register_not_met():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234, "r0": 3})
    session = _FakeSession(probe)
    cond = {
        "condition_symbol": None,
        "condition_register": "r0",
        "condition_op": "eq",
        "condition_value": 5,
    }
    assert _evaluate_condition(session, cond) is False


def test_evaluate_condition_register_gt():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234, "r0": 10})
    session = _FakeSession(probe)
    cond = {
        "condition_symbol": None,
        "condition_register": "r0",
        "condition_op": "gt",
        "condition_value": 7,
    }
    assert _evaluate_condition(session, cond) is True


def test_evaluate_condition_unknown_register_returns_true():
    """Unknown register - don't skip (safe default)."""
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234})
    session = _FakeSession(probe)
    cond = {
        "condition_symbol": None,
        "condition_register": "r99",
        "condition_op": "eq",
        "condition_value": 0,
    }
    assert _evaluate_condition(session, cond) is True


def test_evaluate_condition_symbol_met():
    """Symbol 'counter' at 0x20000100 holds value 0x0000000A (10)."""

    class _ElfWithCounter(_FakeElf):
        pass

    class _ProbeWithMemory(_FakeProbeStaticRegister):
        def read_memory(self, address, size):
            if address == 0x20000100:
                return (10).to_bytes(size, "little")
            return b"\x00" * size

    probe = _ProbeWithMemory(0x08001234, {"pc": 0x08001234, "r0": 0})
    session = _FakeSession(probe, elf=_ElfWithCounter())
    cond = {
        "condition_symbol": "counter",
        "condition_register": None,
        "condition_op": "ge",
        "condition_value": 10,
    }
    assert _evaluate_condition(session, cond) is True


def test_evaluate_condition_symbol_elf_not_loaded_returns_true():
    """ELF not loaded - don't skip."""
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234, "r0": 0})
    session = _FakeSession(probe, elf=_FakeElfNotLoaded())
    cond = {
        "condition_symbol": "counter",
        "condition_register": None,
        "condition_op": "eq",
        "condition_value": 5,
    }
    assert _evaluate_condition(session, cond) is True


def test_evaluate_condition_no_spec_returns_true():
    """No condition_symbol or condition_register - always halt."""
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234})
    session = _FakeSession(probe)
    cond = {
        "condition_symbol": None,
        "condition_register": None,
        "condition_op": "eq",
        "condition_value": 0,
    }
    assert _evaluate_condition(session, cond) is True


# ---------------------------------------------------------------------------
# continue_target with conditional breakpoints
# ---------------------------------------------------------------------------


def test_continue_target_no_conditions_halts_immediately():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234, "r0": 99})
    session = _FakeSession(probe)
    result = continue_target(session)
    assert result["status"] == "ok"
    assert "condition_skip_count" not in result


def test_continue_target_skips_then_halts():
    """r0 is 3 on first two hits, then 5 on the third. Condition: r0==5."""
    bp_addr = 0x08001234
    probe = _FakeProbeSequentialRegister(
        halt_pc=bp_addr,
        register_sequence=[
            {"pc": bp_addr, "r0": 3},
            {"pc": bp_addr, "r0": 3},
            {"pc": bp_addr, "r0": 5},
        ],
    )
    session = _FakeSession(probe)
    session.conditional_breakpoints[bp_addr] = {
        "condition_symbol": None,
        "condition_register": "r0",
        "condition_op": "eq",
        "condition_value": 5,
    }
    result = continue_target(session)
    assert result["status"] == "ok"
    assert result.get("condition_skip_count") == 2


def test_continue_target_halts_immediately_when_condition_met():
    """First hit already satisfies condition - no skips."""
    bp_addr = 0x08001234
    probe = _FakeProbeStaticRegister(bp_addr, {"pc": bp_addr, "r0": 5})
    session = _FakeSession(probe)
    session.conditional_breakpoints[bp_addr] = {
        "condition_symbol": None,
        "condition_register": "r0",
        "condition_op": "eq",
        "condition_value": 5,
    }
    result = continue_target(session)
    assert result["status"] == "ok"
    assert "condition_skip_count" not in result


# ---------------------------------------------------------------------------
# set_breakpoint / clear_breakpoint / clear_all_breakpoints
# ---------------------------------------------------------------------------


def test_set_breakpoint_registers_condition():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234})
    probe._connected = True
    session = _FakeSession(probe)

    result = set_breakpoint(
        session,
        address=0x08001234,
        condition_register="r0",
        condition_op="eq",
        condition_value=5,
        confirm=True,
    )
    assert result["conditional"] is True
    assert 0x08001234 in session.conditional_breakpoints
    cond = session.conditional_breakpoints[0x08001234]
    assert cond["condition_register"] == "r0"
    assert cond["condition_value"] == 5


def test_set_breakpoint_no_condition_does_not_register():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234})
    session = _FakeSession(probe)

    set_breakpoint(session, address=0x08001234, confirm=True)
    assert 0x08001234 not in session.conditional_breakpoints


def test_set_breakpoint_invalid_op_returns_error():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234})
    session = _FakeSession(probe)

    result = set_breakpoint(
        session, address=0x08001234, condition_register="r0", condition_op="invalid"
    )
    assert result["status"] == "error"


def test_clear_breakpoint_removes_condition():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234})
    session = _FakeSession(probe)
    session.conditional_breakpoints[0x08001234] = {"condition_register": "r0"}

    clear_breakpoint(session, address=0x08001234, confirm=True)
    assert 0x08001234 not in session.conditional_breakpoints


def test_clear_all_breakpoints_clears_conditions():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234})
    session = _FakeSession(probe)
    session.conditional_breakpoints[0x08001234] = {"condition_register": "r0"}
    session.conditional_breakpoints[0x08005678] = {"condition_register": "r1"}

    clear_all_breakpoints(session, confirm=True)
    assert session.conditional_breakpoints == {}


def test_list_conditional_breakpoints_empty():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234})
    session = _FakeSession(probe)
    result = list_conditional_breakpoints(session)
    assert result["status"] == "ok"
    assert result["conditional_breakpoints"] == []


def test_list_conditional_breakpoints_with_entries():
    probe = _FakeProbeStaticRegister(0x08001234, {"pc": 0x08001234})
    session = _FakeSession(probe)
    entry = {"condition_register": "r0", "condition_op": "eq", "condition_value": 5}
    session.conditional_breakpoints[0x08001234] = entry

    result = list_conditional_breakpoints(session)
    assert len(result["conditional_breakpoints"]) == 1
    assert result["conditional_breakpoints"][0] is entry


# ---------------------------------------------------------------------------
# continue_until integration (verifies refactor preserved semantics)
# ---------------------------------------------------------------------------


class _FakeSessionForContinueUntil:
    """Session with probe only (no elf, no conditional_breakpoints needed by continue_until)."""

    def __init__(self, probe):
        self.probe = probe
        self.elf = _FakeElfNotLoaded()
        # continue_until does NOT use session.conditional_breakpoints - it manages its own loop
        self.conditional_breakpoints: dict = {}


def test_continue_until_no_condition_halts_immediately():
    """Without condition, continue_until stops on first PC match."""
    bp_addr = 0x08001234
    probe = _FakeProbeStaticRegister(bp_addr, {"pc": bp_addr, "r0": 0})
    session = _FakeSessionForContinueUntil(probe)

    result = continue_until(session, address=bp_addr)
    assert result["status"] == "ok"
    assert result["condition_met"] is True
    assert result["hit_count"] == 1
    assert result["breakpoint_address"] == hex(bp_addr)


def test_continue_until_with_register_condition_skips_until_met():
    """r0==2 on first breakpoint hit, r0==5 on second. Condition: r0==5.

    continue_until calls read_core_registers twice per iteration (PC check + condition
    eval), so the sequence must cover both calls per hit.
    Hit 1: calls [0]=r0:2 for PC, [1]=r0:2 for condition - not met.
    Hit 2: calls [2]=r0:5 for PC, [3]=r0:5 for condition - met - hit_count==2.
    """
    bp_addr = 0x08001234
    probe = _FakeProbeSequentialRegister(
        halt_pc=bp_addr,
        register_sequence=[
            {"pc": bp_addr, "r0": 2},  # hit 1, PC check
            {"pc": bp_addr, "r0": 2},  # hit 1, condition eval
            {"pc": bp_addr, "r0": 5},  # hit 2, PC check
            {"pc": bp_addr, "r0": 5},  # hit 2, condition eval
        ],
    )
    session = _FakeSessionForContinueUntil(probe)

    result = continue_until(
        session,
        address=bp_addr,
        condition_register="r0",
        condition_op="eq",
        condition_value=5,
    )
    assert result["condition_met"] is True
    assert result["hit_count"] == 2


def test_continue_until_max_hits_exceeded():
    """Condition never met - returns max_hits_reached after max_hits iterations."""
    bp_addr = 0x08001234
    # r0 always 0, condition is r0==99 - never true
    probe = _FakeProbeStaticRegister(bp_addr, {"pc": bp_addr, "r0": 0})
    session = _FakeSessionForContinueUntil(probe)

    result = continue_until(
        session,
        address=bp_addr,
        condition_register="r0",
        condition_op="eq",
        condition_value=99,
        max_hits=3,
    )
    assert result["status"] == "ok"
    assert result["condition_met"] is False
    assert result["stop_reason"] == "max_hits_reached"
    assert result["hit_count"] == 3


def test_continue_until_invalid_op_returns_error():
    bp_addr = 0x08001234
    probe = _FakeProbeStaticRegister(bp_addr, {"pc": bp_addr, "r0": 0})
    session = _FakeSessionForContinueUntil(probe)

    result = continue_until(session, address=bp_addr, condition_register="r0", condition_op="bad")
    assert result["status"] == "error"
