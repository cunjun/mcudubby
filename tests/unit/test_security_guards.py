from __future__ import annotations

from types import SimpleNamespace

from McuBuddy.config import RuntimeConfig
from McuBuddy.security_guards import (
    ensure_file_allowed,
    ensure_flash_erase_allowed,
    ensure_memory_read_allowed,
    ensure_memory_write_allowed,
    ensure_rtt_scan_allowed,
)
from McuBuddy.tools.probe import erase_flash, read_memory, write_memory


def test_memory_read_limit_blocks_large_read() -> None:
    config = RuntimeConfig()
    config.memory.max_read_size = 4

    result = ensure_memory_read_allowed(config, 8)

    assert result is not None
    assert result["status"] == "error"
    assert result["security"]["guard"] == "memory.max_read_size"


def test_memory_write_disabled_by_default() -> None:
    result = ensure_memory_write_allowed(RuntimeConfig(), 1)

    assert result is not None
    assert result["security"]["guard"] == "memory.allow_write"


def test_flash_erase_disabled_by_default() -> None:
    result = ensure_flash_erase_allowed(RuntimeConfig())

    assert result is not None
    assert result["security"]["guard"] == "flash.allow_erase"


def test_allowed_file_paths_normalizes_candidate(tmp_path) -> None:
    root = tmp_path / "firmware"
    root.mkdir()
    elf = root / "app.axf"
    elf.write_bytes(b"elf")
    config = RuntimeConfig()
    config.security.allowed_file_paths = [str(root)]

    assert ensure_file_allowed(config, elf) is None

    other = tmp_path / "other.axf"
    other.write_bytes(b"elf")
    result = ensure_file_allowed(config, other)
    assert result is not None
    assert result["security"]["guard"] == "security.allowed_file_paths"


def test_write_memory_guard_runs_before_backend_when_confirmed() -> None:
    probe = SimpleNamespace(calls=[], write_memory=lambda address, data: probe.calls.append(data))
    session = SimpleNamespace(probe=probe, config=RuntimeConfig())

    result = write_memory(session, address=0x20000000, data=[1], confirm=True)

    assert result["status"] == "error"
    assert result["security"]["guard"] == "memory.allow_write"
    assert probe.calls == []


def test_read_memory_guard_runs_before_backend() -> None:
    probe = SimpleNamespace(calls=[], read_memory=lambda address, size: probe.calls.append(size))
    config = RuntimeConfig()
    config.memory.max_read_size = 1
    session = SimpleNamespace(probe=probe, config=config)

    result = read_memory(session, address=0x20000000, size=2)

    assert result["status"] == "error"
    assert result["security"]["guard"] == "memory.max_read_size"
    assert probe.calls == []


def test_erase_flash_guard_runs_after_confirmation_before_backend() -> None:
    probe = SimpleNamespace(calls=[], erase_flash=lambda **kwargs: probe.calls.append(kwargs))
    session = SimpleNamespace(probe=probe, config=RuntimeConfig())

    result = erase_flash(session, chip_erase=True, confirm=True)

    assert result["status"] == "error"
    assert result["security"]["guard"] == "flash.allow_erase"
    assert probe.calls == []


def test_rtt_scan_limit_blocks_large_scan() -> None:
    config = RuntimeConfig()
    config.security.max_rtt_scan_size = 256

    result = ensure_rtt_scan_allowed(config, 512)

    assert result is not None
    assert result["security"]["guard"] == "security.max_rtt_scan_size"
