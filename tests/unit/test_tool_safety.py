from mcudubby.tool_safety import (
    TOOL_SAFETY,
    get_tool_safety,
    list_tool_safety,
    require_tool_confirmation,
)
from mcudubby.tools.probe import (
    read_mpu_regions,
    set_breakpoint,
    set_watchpoint,
    write_memory,
    write_symbol_value,
)
from mcudubby.tools.svd import svd_write_register


class _RecordingProbe:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def write_memory(self, address: int, data: bytes) -> None:
        self.calls.append(f"write_memory:{hex(address)}:{data.hex()}")

    def set_breakpoint(self, address: int) -> dict:
        self.calls.append(f"set_breakpoint:{hex(address)}")
        return {"status": "ok", "address": hex(address)}

    def set_watchpoint(self, address: int, size: int = 4, watch_type: str = "write") -> dict:
        self.calls.append(f"set_watchpoint:{hex(address)}:{size}:{watch_type}")
        return {"status": "ok", "address": hex(address)}


class _FakeElf:
    is_loaded = True

    def resolve_symbol(self, name: str) -> dict:
        return {"address": "0x20000000", "source": None}


class _FakeSvd:
    is_loaded = True

    def __init__(self) -> None:
        self.calls: list[str] = []

    def write_register(self, peripheral: str, register: str, value: int, probe) -> dict:
        self.calls.append(f"{peripheral}.{register}={value}")
        return {"status": "ok"}


class _FakeSession:
    def __init__(self) -> None:
        self.probe = _RecordingProbe()
        self.elf = _FakeElf()
        self.svd = _FakeSvd()
        self.conditional_breakpoints = {}


def test_tool_safety_marks_read_only_and_destructive_tools() -> None:
    assert get_tool_safety("doctor")["level"] == "read-only"
    assert get_tool_safety("first_contact")["level"] == "read-only"
    assert get_tool_safety("probe_reset")["level"] == "execution-changing"
    assert get_tool_safety("probe_write_memory")["level"] == "state-changing"
    assert get_tool_safety("probe_read_mpu_regions")["level"] == "state-changing"
    assert get_tool_safety("erase_flash")["level"] == "persistent-destructive"
    assert get_tool_safety("program_flash")["level"] == "persistent-destructive"


def test_list_tool_safety_is_machine_readable() -> None:
    result = list_tool_safety()

    assert result["status"] == "ok"
    assert result["safety_levels"]["read-only"]["requires_confirmation"] is False
    assert result["safety_levels"]["persistent-destructive"]["requires_confirmation"] is True
    assert "erase_flash" in result["tools"]
    assert result["tools"]["erase_flash"]["level"] == "persistent-destructive"
    assert set(TOOL_SAFETY).issuperset({"doctor", "first_contact", "board_smoke_test"})


def test_require_tool_confirmation_blocks_confirmed_tools_by_default() -> None:
    result = require_tool_confirmation("erase_flash", confirmed=False)

    assert result is not None
    assert result["status"] == "error"
    assert result["safety"]["level"] == "persistent-destructive"
    assert result["safety"]["requires_confirmation"] is True


def test_require_tool_confirmation_allows_confirmed_or_read_only_tools() -> None:
    assert require_tool_confirmation("erase_flash", confirmed=True) is None
    assert require_tool_confirmation("doctor", confirmed=False) is None


def test_state_changing_probe_write_memory_requires_confirmation() -> None:
    session = _FakeSession()

    result = write_memory(session, address=0x20000000, data=[1, 2, 3])

    assert result["status"] == "error"
    assert result["safety"]["level"] == "state-changing"
    assert session.probe.calls == []


def test_state_changing_symbol_write_requires_confirmation() -> None:
    session = _FakeSession()

    result = write_symbol_value(session, name="g_state", value=1)

    assert result["status"] == "error"
    assert result["safety"]["level"] == "state-changing"
    assert session.probe.calls == []


def test_state_changing_svd_write_requires_confirmation() -> None:
    session = _FakeSession()

    result = svd_write_register(session, peripheral="GPIOA", register="ODR", value=1)

    assert result["status"] == "error"
    assert result["safety"]["level"] == "state-changing"
    assert session.svd.calls == []


def test_state_changing_breakpoint_and_watchpoint_require_confirmation() -> None:
    session = _FakeSession()

    breakpoint_result = set_breakpoint(session, address=0x08000000)
    watchpoint_result = set_watchpoint(session, address=0x20000000)

    assert breakpoint_result["status"] == "error"
    assert watchpoint_result["status"] == "error"
    assert session.probe.calls == []


def test_mpu_region_read_requires_confirmation_because_it_writes_selector() -> None:
    session = _FakeSession()

    result = read_mpu_regions(session)

    assert result["status"] == "error"
    assert result["safety"]["level"] == "state-changing"
    assert session.probe.calls == []
