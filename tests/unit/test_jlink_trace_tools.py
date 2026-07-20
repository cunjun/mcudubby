from __future__ import annotations

from types import SimpleNamespace

import McuBubby.backends.probe.jlink_backend as jlink_backend
from McuBubby.tools.probe import read_cycle_counter, read_itm_trace, read_swo_log


class _FakeJLink:
    def __init__(self, lib=None) -> None:
        self._memory = {
            0xE000EDFC: 0x00000000,
            0xE0001000: 0x00000000,
            0xE0001004: 0x00123456,
        }
        self.write32_calls: list[tuple[int, list[int]]] = []
        self._swo_enabled = False
        self._swo_buffer = list(b"SWO hello\n")

    def open(self, serial_no=None) -> None:
        return None

    def set_tif(self, interface) -> None:
        self.interface = interface

    def connect(self, target: str, speed=None) -> None:
        self.target = target

    def close(self) -> None:
        return None

    def memory_read32(self, address: int, count: int) -> list[int]:
        return [self._memory[address]]

    def memory_write32(self, address: int, data: list[int]) -> None:
        self.write32_calls.append((address, list(data)))
        self._memory[address] = int(data[0])

    def swo_enabled(self) -> bool:
        return self._swo_enabled

    def swo_enable(self, cpu_speed, swo_speed=9600, port_mask=0x01) -> None:
        self._swo_enabled = True
        self.swo_enable_args = (cpu_speed, swo_speed, port_mask)
        self.swo_enable_calls = getattr(self, "swo_enable_calls", 0) + 1

    def swo_num_bytes(self) -> int:
        return len(self._swo_buffer)

    def swo_read(self, offset, num_bytes, remove=False):
        data = self._swo_buffer[offset : offset + num_bytes]
        if remove:
            del self._swo_buffer[: len(data)]
        return list(data)

    def swo_read_stimulus(self, port, num_bytes):
        data = self._swo_buffer[:num_bytes]
        del self._swo_buffer[: len(data)]
        return list(data)


def _fake_library_module():
    return SimpleNamespace(Library=lambda path: object())


def _fake_pylink_module(fake):
    def _make_jlink(lib=None):
        return fake

    return SimpleNamespace(
        JLink=_make_jlink,
        enums=SimpleNamespace(JLinkInterfaces=SimpleNamespace(SWD="SWD")),
    )


def test_jlink_backend_read_cycle_counter_enables_dwt(monkeypatch) -> None:
    fake = _FakeJLink()
    monkeypatch.setattr(jlink_backend, "pylink", _fake_pylink_module(fake))
    monkeypatch.setattr(jlink_backend, "pylink_library", _fake_library_module())
    monkeypatch.setattr(
        jlink_backend.JLinkProbeBackend,
        "_resolve_dll_path",
        classmethod(lambda cls, dll_path=None: dll_path or "E:/software/jlink/JLink_x64.dll"),
    )

    backend = jlink_backend.JLinkProbeBackend(dll_path="E:/software/jlink/JLink_x64.dll")
    backend.connect(target="STM32F103C8")

    result = backend.read_cycle_counter()

    assert result["status"] == "ok"
    assert result["backend"] == "jlink"
    assert result["cyccnt"] == 0x00123456
    assert result["cyccnt_hex"] == "0x123456"
    assert result["dwt_enabled"] is True
    assert fake._memory[0xE000EDFC] & (1 << 24)
    assert fake._memory[0xE0001000] & 1


def test_jlink_backend_read_cycle_counter_does_not_rewrite_when_enabled(monkeypatch) -> None:
    fake = _FakeJLink()
    fake._memory[0xE000EDFC] = 1 << 24
    fake._memory[0xE0001000] = 1
    monkeypatch.setattr(jlink_backend, "pylink", _fake_pylink_module(fake))
    monkeypatch.setattr(jlink_backend, "pylink_library", _fake_library_module())
    monkeypatch.setattr(
        jlink_backend.JLinkProbeBackend,
        "_resolve_dll_path",
        classmethod(lambda cls, dll_path=None: dll_path or "E:/software/jlink/JLink_x64.dll"),
    )

    backend = jlink_backend.JLinkProbeBackend(dll_path="E:/software/jlink/JLink_x64.dll")
    backend.connect(target="STM32F103C8")

    result = backend.read_cycle_counter()

    assert result["status"] == "ok"
    assert fake.write32_calls == []


def test_read_cycle_counter_reports_unsupported_backend() -> None:
    session = SimpleNamespace(probe=SimpleNamespace())

    result = read_cycle_counter(session)

    assert result["status"] == "error"
    assert "does not support" in result["summary"]


def test_jlink_backend_read_swo_log_enables_and_reads(monkeypatch) -> None:
    fake = _FakeJLink()
    monkeypatch.setattr(jlink_backend, "pylink", _fake_pylink_module(fake))
    monkeypatch.setattr(jlink_backend, "pylink_library", _fake_library_module())
    monkeypatch.setattr(
        jlink_backend.JLinkProbeBackend,
        "_resolve_dll_path",
        classmethod(lambda cls, dll_path=None: dll_path or "E:/software/jlink/JLink_x64.dll"),
    )

    backend = jlink_backend.JLinkProbeBackend(dll_path="E:/software/jlink/JLink_x64.dll")
    backend.connect(target="STM32F103C8")

    result = backend.read_swo_log(cpu_speed_hz=72000000, swo_speed_hz=2000000, max_bytes=16)

    assert result["status"] == "ok"
    assert result["backend"] == "jlink"
    assert result["bytes_available"] == 10
    assert result["bytes_read"] == 10
    assert result["text"] == "SWO hello\n"
    assert fake.swo_enable_args == (72000000, 2000000, 0x01)


def test_jlink_backend_read_swo_log_reconfigures_when_parameters_change(monkeypatch) -> None:
    fake = _FakeJLink()
    monkeypatch.setattr(jlink_backend, "pylink", _fake_pylink_module(fake))
    monkeypatch.setattr(jlink_backend, "pylink_library", _fake_library_module())
    monkeypatch.setattr(
        jlink_backend.JLinkProbeBackend,
        "_resolve_dll_path",
        classmethod(lambda cls, dll_path=None: dll_path or "E:/software/jlink/JLink_x64.dll"),
    )

    backend = jlink_backend.JLinkProbeBackend(dll_path="E:/software/jlink/JLink_x64.dll")
    backend.connect(target="STM32F103C8")

    backend.read_swo_log(cpu_speed_hz=72000000, swo_speed_hz=2000000, max_bytes=16)
    fake._swo_buffer = list(b"AB")
    result = backend.read_swo_log(
        cpu_speed_hz=72000000, swo_speed_hz=1000000, max_bytes=16, port_mask=0x03
    )

    assert result["status"] == "ok"
    assert fake.swo_enable_calls == 2
    assert fake.swo_enable_args == (72000000, 1000000, 0x03)


def test_read_swo_log_reports_unsupported_backend() -> None:
    session = SimpleNamespace(probe=SimpleNamespace())

    result = read_swo_log(session, cpu_speed_hz=72000000, swo_speed_hz=2000000)

    assert result["status"] == "error"
    assert "does not support" in result["summary"]


def test_jlink_backend_read_itm_trace_reads_specific_port(monkeypatch) -> None:
    fake = _FakeJLink()
    monkeypatch.setattr(jlink_backend, "pylink", _fake_pylink_module(fake))
    monkeypatch.setattr(jlink_backend, "pylink_library", _fake_library_module())
    monkeypatch.setattr(
        jlink_backend.JLinkProbeBackend,
        "_resolve_dll_path",
        classmethod(lambda cls, dll_path=None: dll_path or "E:/software/jlink/JLink_x64.dll"),
    )

    backend = jlink_backend.JLinkProbeBackend(dll_path="E:/software/jlink/JLink_x64.dll")
    backend.connect(target="STM32F103C8")

    result = backend.read_itm_trace(
        cpu_speed_hz=72000000,
        swo_speed_hz=2000000,
        stimulus_port=2,
        max_bytes=16,
    )

    assert result["status"] == "ok"
    assert result["stimulus_port"] == 2
    assert result["port_mask"] == 0x04
    assert result["bytes_read"] == 10
    assert result["text"] == "SWO hello\n"
    assert fake.swo_enable_args == (72000000, 2000000, 0x04)


def test_read_itm_trace_reports_unsupported_backend() -> None:
    session = SimpleNamespace(probe=SimpleNamespace())

    result = read_itm_trace(
        session,
        cpu_speed_hz=72000000,
        swo_speed_hz=2000000,
        stimulus_port=1,
    )

    assert result["status"] == "error"
    assert "does not support" in result["summary"]
