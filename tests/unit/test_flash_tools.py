from __future__ import annotations

from types import SimpleNamespace

from McuBubby.backends.probe.pyocd_backend import PyOcdProbeBackend
from McuBubby.tools.probe import erase_flash, program_flash, verify_flash


class _FakeFlash:
    class Operation:
        ERASE = "erase"
        PROGRAM = "program"

    def __init__(self) -> None:
        self.init_calls: list[tuple[str, int | None]] = []
        self.uninit_calls = 0
        self.erase_all_calls = 0
        self.erase_sector_calls: list[int] = []
        self.program_page_calls: list[tuple[int, bytes]] = []

    def init(self, operation, address=None, clock=0, reset=False) -> None:
        self.init_calls.append((operation, address))

    def uninit(self) -> None:
        self.uninit_calls += 1

    def cleanup(self) -> None:
        self.uninit_calls += 1

    def erase_all(self) -> None:
        self.erase_all_calls += 1

    def erase_sector(self, address: int) -> None:
        self.erase_sector_calls.append(address)

    def get_sector_info(self, address: int):
        return SimpleNamespace(size=0x100)

    def get_page_info(self, address: int):
        return SimpleNamespace(size=0x100)

    def program_page(self, address: int, data: bytes) -> None:
        self.program_page_calls.append((address, bytes(data)))


class _FakeTarget:
    def __init__(self, flash: _FakeFlash) -> None:
        self.flash = flash


def test_backend_chip_erase_calls_flash_erase_all() -> None:
    flash = _FakeFlash()
    backend = PyOcdProbeBackend()
    backend._target = _FakeTarget(flash)

    result = backend.erase_flash(chip_erase=True)

    assert result["status"] == "ok"
    assert flash.init_calls == [("erase", None)]
    assert flash.erase_all_calls == 1
    assert flash.uninit_calls == 1


def test_backend_range_erase_walks_sectors() -> None:
    flash = _FakeFlash()
    backend = PyOcdProbeBackend()
    backend._target = _FakeTarget(flash)

    result = backend.erase_flash(start_address=0x08000000, end_address=0x08000200)

    assert result["status"] == "ok"
    assert flash.init_calls == [("erase", 0x08000000)]
    assert flash.erase_sector_calls == [0x08000000, 0x08000100]
    assert flash.uninit_calls == 1


def test_program_flash_converts_list_and_verifies() -> None:
    probe = SimpleNamespace(
        program_flash=lambda address, data, verify: {
            "status": "ok",
            "summary": "ok",
            "address": hex(address),
            "size": len(data),
            "verify": verify,
            "payload": data,
        }
    )
    session = SimpleNamespace(probe=probe)

    result = program_flash(
        session,
        address=0x08000000,
        data=[1, 2, 3],
        verify=True,
        confirm=True,
    )

    assert result["status"] == "ok"
    assert result["payload"] == b"\x01\x02\x03"


def test_erase_flash_requires_confirmation_before_touching_probe() -> None:
    probe = SimpleNamespace(
        calls=[],
        erase_flash=lambda **kwargs: probe.calls.append(kwargs),
    )
    session = SimpleNamespace(probe=probe)

    result = erase_flash(session, chip_erase=True)

    assert result["status"] == "error"
    assert result["safety"]["requires_confirmation"] is True
    assert probe.calls == []


def test_program_flash_requires_confirmation_before_touching_probe() -> None:
    probe = SimpleNamespace(
        calls=[],
        program_flash=lambda **kwargs: probe.calls.append(kwargs),
    )
    session = SimpleNamespace(probe=probe)

    result = program_flash(session, address=0x08000000, data=[1, 2, 3])

    assert result["status"] == "error"
    assert result["safety"]["requires_confirmation"] is True
    assert probe.calls == []


def test_verify_flash_reports_first_mismatch() -> None:
    flash = _FakeFlash()
    backend = PyOcdProbeBackend()
    backend._target = _FakeTarget(flash)
    backend.read_memory = lambda address, size: b"\x01\xff\x03"

    result = backend.verify_flash(0x08000000, b"\x01\x02\x03")

    assert result["status"] == "error"
    assert result["match"] is False
    assert result["mismatch_count"] == 1
    assert result["first_mismatch_address"] == hex(0x08000001)


def test_verify_flash_tool_converts_list_input() -> None:
    probe = SimpleNamespace(
        verify_flash=lambda address, data: {
            "status": "ok",
            "summary": "verified",
            "address": hex(address),
            "size": len(data),
            "match": True,
            "payload": data,
        }
    )
    session = SimpleNamespace(probe=probe)

    result = verify_flash(session, address=0x08000000, data=[0xAA, 0x55])

    assert result["status"] == "ok"
    assert result["payload"] == b"\xaa\x55"
