from __future__ import annotations

from types import SimpleNamespace

import McuBubby.backends.probe.pyocd_backend as pyocd_backend_module
from McuBubby.backends.probe.pyocd_backend import PyOcdProbeBackend
from McuBubby.tools.probe import read_fpu_registers


class _FakeProbe:
    def read_fpu_registers(self) -> dict:
        return {
            "s0": 1.5,
            "s1": 2.25,
            "fpscr": 0x10,
        }


class _FakeTarget:
    def __init__(self) -> None:
        self.set_calls: list[tuple[int, int, object]] = []
        self.remove_calls: list[tuple[int, int, object]] = []

    def set_watchpoint(self, address: int, size: int, watch_type: object) -> None:
        self.set_calls.append((address, size, watch_type))

    def remove_watchpoint(self, address: int, size: int, watch_type: object) -> None:
        self.remove_calls.append((address, size, watch_type))


def test_read_fpu_registers_keeps_float_values() -> None:
    session = SimpleNamespace(probe=_FakeProbe())

    result = read_fpu_registers(session)

    assert result["status"] == "ok"
    assert result["registers"]["s0"] == 1.5
    assert result["registers"]["s1"] == 2.25
    assert result["registers"]["fpscr"] == "0x10"


def test_watchpoint_remove_uses_saved_size_and_type(monkeypatch) -> None:
    fake_target = _FakeTarget()
    backend = PyOcdProbeBackend()
    backend._target = fake_target

    fake_target_enum = SimpleNamespace(
        WatchpointType=SimpleNamespace(READ="R", WRITE="W", READ_WRITE="RW")
    )
    monkeypatch.setattr(pyocd_backend_module, "Target", fake_target_enum)

    result = backend.set_watchpoint(0x20000000, 4, "write")

    assert result["status"] == "ok"
    remove_result = backend.remove_watchpoint(0x20000000)
    assert remove_result["status"] == "ok"
    assert fake_target.set_calls == [(0x20000000, 4, "W")]
    assert fake_target.remove_calls == [(0x20000000, 4, "W")]


def test_clear_all_watchpoints_uses_saved_metadata(monkeypatch) -> None:
    fake_target = _FakeTarget()
    backend = PyOcdProbeBackend()
    backend._target = fake_target

    fake_target_enum = SimpleNamespace(
        WatchpointType=SimpleNamespace(READ="R", WRITE="W", READ_WRITE="RW")
    )
    monkeypatch.setattr(pyocd_backend_module, "Target", fake_target_enum)

    backend.set_watchpoint(0x20000000, 4, "write")
    backend.set_watchpoint(0x20000010, 2, "read")

    result = backend.clear_all_watchpoints()

    assert result["status"] == "ok"
    assert result["cleared_count"] == 2
    assert fake_target.remove_calls == [
        (0x20000000, 4, "W"),
        (0x20000010, 2, "R"),
    ]
