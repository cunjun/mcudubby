from __future__ import annotations

from types import SimpleNamespace

from McuBuddy.backends.probe.pyocd_backend import PyOcdProbeBackend
from McuBuddy.backends.probe.base import ProbeCapability
from McuBuddy.config import RuntimeConfig
from McuBuddy.tools import probe as probe_tools
from McuBuddy.tools.probe import erase_flash, program_flash, verify_flash


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
        return SimpleNamespace(size=0x100, base_addr=address & ~0xFF)

    def get_page_info(self, address: int):
        return SimpleNamespace(size=0x100, base_addr=address & ~0xFF)

    def program_page(self, address: int, data: bytes) -> None:
        self.program_page_calls.append((address, bytes(data)))


class _FakeTarget:
    def __init__(self, flash: _FakeFlash) -> None:
        self.flash = flash
        self.reset_calls = 0

    def reset(self) -> None:
        self.reset_calls += 1


def test_backend_flash_image_erases_programs_verifies_then_resets() -> None:
    flash = _FakeFlash()
    target = _FakeTarget(flash)
    backend = PyOcdProbeBackend()
    backend._target = target
    backend.read_memory = lambda address, size: b"\x01\x02\x03"

    flash_image = getattr(backend, "flash_image", None)
    assert callable(flash_image), "probe backend must expose the high-level flash_image transaction"

    result = flash_image(
        address=0x08000080,
        data=b"\x01\x02\x03",
        erase_mode="sector",
        verify=True,
        reset_after=True,
    )

    assert result["status"] == "ok"
    assert result["erased"] is True
    assert result["verified"] is True
    assert result["reset"] is True
    assert flash.init_calls == [("erase", 0x08000000), ("program", 0x08000080)]
    assert flash.erase_sector_calls == [0x08000000]
    assert flash.program_page_calls == [(0x08000080, b"\x01\x02\x03")]
    assert target.reset_calls == 1


def test_backend_flash_image_does_not_program_across_page_boundaries() -> None:
    flash = _FakeFlash()
    backend = PyOcdProbeBackend()
    backend._target = _FakeTarget(flash)
    payload = bytes(index & 0xFF for index in range(0x180))

    result = backend.flash_image(
        address=0x08000080,
        data=payload,
        erase_mode="sector",
        verify=False,
        reset_after=False,
    )

    assert result["status"] == "ok"
    assert flash.program_page_calls == [
        (0x08000080, payload[:0x80]),
        (0x08000100, payload[0x80:]),
    ]


def test_backend_flash_image_does_not_reset_after_verification_mismatch() -> None:
    flash = _FakeFlash()
    target = _FakeTarget(flash)
    backend = PyOcdProbeBackend()
    backend._target = target
    backend.read_memory = lambda address, size: b"\xff" * size

    result = backend.flash_image(
        address=0x08000000,
        data=b"\x01\x02",
        erase_mode="sector",
        verify=True,
        reset_after=True,
    )

    assert result["status"] == "error"
    assert result["stage"] == "verify"
    assert result["erased"] is True
    assert result["programmed"] is True
    assert result["verified"] is False
    assert result["reset"] is False
    assert target.reset_calls == 0


def test_backend_flash_image_reports_partial_sector_erase_truthfully() -> None:
    class _FailingFlash(_FakeFlash):
        def erase_sector(self, address: int) -> None:
            if self.erase_sector_calls:
                raise RuntimeError("erase failed")
            super().erase_sector(address)

    flash = _FailingFlash()
    backend = PyOcdProbeBackend()
    backend._target = _FakeTarget(flash)

    result = backend.flash_image(
        address=0x08000000,
        data=b"\xaa" * 0x180,
        erase_mode="sector",
        verify=False,
        reset_after=False,
    )

    assert result["status"] == "error"
    assert result["stage"] == "erase"
    assert result["erased"] is False
    assert result["erase_state"] == "partial"
    assert result["erased_sector_count"] == 1
    assert result["program_state"] == "not_started"


def test_backend_flash_image_reports_cleanup_failure() -> None:
    class _CleanupFailingFlash(_FakeFlash):
        def cleanup(self) -> None:
            raise RuntimeError("cleanup failed")

    flash = _CleanupFailingFlash()
    backend = PyOcdProbeBackend()
    backend._target = _FakeTarget(flash)

    result = backend.flash_image(
        address=0x08000000,
        data=b"\xaa",
        erase_mode="sector",
        verify=False,
        reset_after=False,
    )

    assert result["status"] == "error"
    assert result["stage"] == "erase_cleanup"
    assert result["erased"] is True
    assert result["erase_state"] == "complete"
    assert result["program_state"] == "not_started"


def test_flash_image_tool_reads_only_an_allowed_confirmed_file(tmp_path) -> None:
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"\xaa\x55")
    calls: list[dict] = []
    probe = SimpleNamespace(flash_image=lambda **kwargs: calls.append(kwargs) or {"status": "ok"})
    config = RuntimeConfig()
    config.flash.allow_erase = True
    config.flash.allow_program = True
    config.security.allowed_file_paths = [str(tmp_path)]
    session = SimpleNamespace(probe=probe, config=config)

    flash_image = getattr(probe_tools, "flash_image", None)
    assert callable(flash_image), "probe tools must expose flash_image"

    result = flash_image(
        session,
        path=str(firmware),
        address=0x08000000,
        confirm=True,
    )

    assert result["status"] == "ok"
    assert calls == [
        {
            "address": 0x08000000,
            "data": b"\xaa\x55",
            "erase_mode": "sector",
            "verify": True,
            "reset_after": True,
        }
    ]
    assert result["path"] == str(firmware.resolve())
    assert result["size"] == 2


def test_flash_image_tool_blocks_before_reading_or_touching_probe(tmp_path) -> None:
    outside = tmp_path / "outside" / "firmware.bin"
    outside.parent.mkdir()
    outside.write_bytes(b"\xaa")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    calls: list[dict] = []
    probe = SimpleNamespace(flash_image=lambda **kwargs: calls.append(kwargs))
    config = RuntimeConfig()
    config.flash.allow_erase = True
    config.flash.allow_program = True
    config.security.allowed_file_paths = [str(allowed)]
    session = SimpleNamespace(probe=probe, config=config)

    flash_image = getattr(probe_tools, "flash_image", None)
    assert callable(flash_image), "probe tools must expose flash_image"

    confirmation_result = flash_image(session, path=str(outside), address=0x08000000)
    path_result = flash_image(
        session,
        path=str(outside),
        address=0x08000000,
        confirm=True,
    )

    assert confirmation_result["safety"]["requires_confirmation"] is True
    assert path_result["security"]["guard"] == "security.allowed_file_paths"
    assert calls == []


def test_flash_image_tool_reports_unsupported_backend_before_reading_file(tmp_path) -> None:
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"\xaa")
    probe = SimpleNamespace(capabilities=frozenset({ProbeCapability.FLASH}))
    config = RuntimeConfig()
    config.flash.allow_erase = True
    config.flash.allow_program = True
    config.probe.backend = "jlink"
    session = SimpleNamespace(probe=probe, config=config)

    result = probe_tools.flash_image(
        session,
        path=str(firmware),
        address=0x08000000,
        confirm=True,
    )

    assert result["status"] == "error"
    assert result["required_capability"] == "flash-image"
    assert result["backend"] == "jlink"


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
