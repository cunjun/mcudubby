from McuBuddy.session import SessionState
from McuBuddy.tools.probe import clear_all_breakpoints
from McuBuddy.tools.probe import clear_breakpoint
from McuBuddy.tools.probe import continue_target
from McuBuddy.tools.probe import read_stopped_context
from McuBuddy.tools.probe import set_breakpoint
from McuBuddy.tools.probe import set_breakpoints_for_function_range


class _FakeBreakpointProbe:
    def __init__(self) -> None:
        self.breakpoints: set[int] = set()
        self.state = "halted"

    def set_breakpoint(self, address: int) -> dict:
        self.breakpoints.add(address)
        return {
            "status": "ok",
            "summary": f"Breakpoint set at {hex(address)}.",
            "address": hex(address),
        }

    def clear_breakpoint(self, address: int) -> dict:
        self.breakpoints.discard(address)
        return {
            "status": "ok",
            "summary": f"Breakpoint cleared at {hex(address)}.",
            "address": hex(address),
        }

    def clear_all_breakpoints(self) -> dict:
        cleared = len(self.breakpoints)
        self.breakpoints.clear()
        return {
            "status": "ok",
            "summary": f"Cleared {cleared} breakpoint(s).",
            "cleared_count": cleared,
        }

    def continue_target(
        self, timeout_seconds: float = 5.0, poll_interval_seconds: float = 0.05
    ) -> dict:
        self.state = "halted"
        return {
            "status": "ok",
            "summary": "Target stopped after continue.",
            "stop_reason": "breakpoint_hit",
            "state": self.state,
            "pc": "0x8001234",
        }

    def get_state(self) -> str:
        return self.state

    def read_core_registers(self) -> dict[str, int]:
        return {
            "pc": 0x08001234,
            "lr": 0x08004567,
            "sp": 0x20001F80,
            "xpsr": 0x21000000,
        }

    def read_fault_registers(self) -> dict[str, int]:
        return {
            "cfsr": 0x0,
            "hfsr": 0x0,
            "mmfar": 0xE000EDF8,
            "bfar": 0xE000EDF8,
            "shcsr": 0x0,
        }


class _FakeElf:
    is_loaded = True

    def resolve_symbol(self, name: str) -> dict:
        if name == "sensor_init":
            return {"symbol": name, "address": "0x8001234", "source": None}
        if name == "main":
            return {"symbol": name, "address": "0x8008805", "source": None}
        return {"symbol": name, "address": None, "source": None}

    def resolve_address(self, address: int) -> dict:
        mapping = {
            0x08001234: {"symbol": "sensor_init", "source": None},
            0x08004567: {"symbol": "main", "source": None},
        }
        return {"address": hex(address), **mapping.get(address, {"symbol": None, "source": None})}

    def list_functions(self) -> list[dict[str, str]]:
        return [
            {"name": "sensor_init", "address": "0x8001234"},
            {"name": "main", "address": "0x8008805"},
        ]


class _FakeLog:
    def read_recent(self, line_count: int = 20) -> list[str]:
        return [
            "boot start",
            "clock init ok",
            "sensor init...",
        ][-line_count:]


def test_set_breakpoint_resolves_symbol_via_elf() -> None:
    session = SessionState()
    session.probe = _FakeBreakpointProbe()
    session.elf = _FakeElf()

    result = set_breakpoint(session, symbol="sensor_init", confirm=True)

    assert result["status"] == "ok"
    assert result["breakpoint"]["symbol"] == "sensor_init"
    assert result["breakpoint"]["address"] == "0x8001234"
    assert 0x08001234 in session.probe.breakpoints


def test_continue_target_returns_symbol_context() -> None:
    session = SessionState()
    session.probe = _FakeBreakpointProbe()
    session.elf = _FakeElf()

    result = continue_target(session, timeout_seconds=1.0, poll_interval_ms=10)

    assert result["status"] == "ok"
    assert result["stop_reason"] == "breakpoint_hit"
    assert result["symbol"] == "sensor_init"


def test_read_stopped_context_includes_symbols_and_logs() -> None:
    session = SessionState()
    session.probe = _FakeBreakpointProbe()
    session.elf = _FakeElf()
    session.log = _FakeLog()

    result = read_stopped_context(
        session,
        include_fault_registers=True,
        include_logs=True,
        log_tail_lines=10,
        resolve_symbols=True,
    )

    assert result["status"] == "ok"
    assert result["symbol_context"]["pc_symbol"] == "sensor_init"
    assert result["symbol_context"]["lr_symbol"] == "main"
    assert result["log_context"]["last_meaningful_line"] == "sensor init..."


def test_clear_breakpoint_and_clear_all_breakpoints() -> None:
    session = SessionState()
    session.probe = _FakeBreakpointProbe()
    session.elf = _FakeElf()

    set_breakpoint(session, symbol="sensor_init", confirm=True)
    clear_breakpoint(session, symbol="sensor_init", confirm=True)
    assert not session.probe.breakpoints

    set_breakpoint(session, address=0x08004567, confirm=True)
    result = clear_all_breakpoints(session, confirm=True)

    assert result["status"] == "ok"
    assert result["cleared_count"] == 1
    assert not session.probe.breakpoints


def test_set_breakpoint_normalizes_thumb_symbol_address() -> None:
    session = SessionState()
    session.probe = _FakeBreakpointProbe()
    session.elf = _FakeElf()

    result = set_breakpoint(session, symbol="main", confirm=True)

    assert result["status"] == "ok"
    assert result["breakpoint"]["address"] == "0x8008804"
    assert 0x08008804 in session.probe.breakpoints


def test_set_breakpoints_for_function_range_requires_confirmation() -> None:
    session = SessionState()
    session.probe = _FakeBreakpointProbe()
    session.elf = _FakeElf()

    result = set_breakpoints_for_function_range(
        session,
        start_symbol="sensor_init",
        end_symbol="main",
    )

    assert result["status"] == "error"
    assert result["safety"]["level"] == "state-changing"
    assert session.probe.breakpoints == set()
