from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from McuBuddy.config import RuntimeConfig
from McuBuddy.elf_manager import ElfManager
from McuBuddy.tools.probe import compare_elf_to_flash, read_memory_map


class _FakeSection:
    def __init__(self, name: str, addr: int, size: int, data: bytes = b"") -> None:
        self.name = name
        self._values = {
            "sh_addr": addr,
            "sh_size": size,
            "sh_type": "SHT_PROGBITS",
            "sh_flags": 0x2,
        }
        self._data = data or bytes(size)

    def __getitem__(self, key: str):
        return self._values[key]

    def data(self) -> bytes:
        return self._data


class _FakeSegment:
    def __init__(self, p_type: str, vaddr: int, paddr: int, memsz: int) -> None:
        self._values = {
            "p_type": p_type,
            "p_vaddr": vaddr,
            "p_paddr": paddr,
            "p_memsz": memsz,
        }

    def __getitem__(self, key: str):
        return self._values[key]


class _FakeElfFile:
    def __init__(self, _handle) -> None:
        pass

    def iter_segments(self):
        return [
            _FakeSegment("PT_LOAD", 0x08000000, 0x08000000, 0x1000),
            _FakeSegment("PT_LOAD", 0x20000000, 0x08001000, 0x200),
        ]

    def iter_sections(self):
        return [
            _FakeSection(".text", 0x08000000, 0x120),
            _FakeSection(".data", 0x20000000, 0x40),
            _FakeSection(".bss", 0x20000040, 0x80),
            _FakeSection(".empty", 0x0, 0),
        ]


def test_elf_manager_get_sections_includes_lma(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("McuBuddy.elf_manager.ELFFile", _FakeElfFile)

    elf_path = tmp_path / "fake.elf"
    elf_path.write_bytes(b"fake")

    manager = ElfManager()
    manager._path = elf_path

    sections = manager.get_sections()

    assert sections == [
        {"name": ".text", "vma": "0x8000000", "lma": "0x8000000", "size": 0x120},
        {"name": ".data", "vma": "0x20000000", "lma": "0x8001000", "size": 0x40},
        {"name": ".bss", "vma": "0x20000040", "lma": "0x8001040", "size": 0x80},
    ]


def test_read_memory_map_uses_elf_get_sections() -> None:
    fake_sections = [
        {"name": ".text", "vma": "0x8000000", "lma": "0x8000000", "size": 256},
    ]
    session = SimpleNamespace(
        elf=SimpleNamespace(
            is_loaded=True,
            get_sections=lambda: fake_sections,
        )
    )

    result = read_memory_map(session)

    assert result["status"] == "ok"
    assert result["sections"] == fake_sections
    assert result["elf_sections_error"] is None


class _MemoryProbe:
    def __init__(self, contents: dict[int, bytes]) -> None:
        self.contents = contents
        self.calls: list[tuple[int, int]] = []

    def read_memory(self, address: int, size: int) -> bytes:
        self.calls.append((address, size))
        for start, data in self.contents.items():
            offset = address - start
            if 0 <= offset and offset + size <= len(data):
                return data[offset : offset + size]
        raise ValueError(f"no test data at {hex(address)}")


def test_compare_elf_to_flash_uses_lma_chunks_and_skips_runtime_ram() -> None:
    sections = [
        {
            "name": "ER_IROM1",
            "vma": 0x08000000,
            "lma": 0x08000000,
            "size": 6,
            "data": b"abcdef",
        },
        {
            "name": "RW_IRAM1",
            "vma": 0x20000000,
            "lma": 0x08000100,
            "size": 4,
            "data": b"init",
        },
        {
            "name": "runtime",
            "vma": 0x20000100,
            "lma": 0x20000100,
            "size": 4,
            "data": b"live",
        },
    ]
    probe = _MemoryProbe({0x08000000: b"abcdef", 0x08000100: b"init"})
    config = RuntimeConfig()
    config.memory.max_read_size = 3
    session = SimpleNamespace(
        elf=SimpleNamespace(is_loaded=True, get_section_data=lambda: sections),
        probe=probe,
        config=config,
    )

    result = compare_elf_to_flash(session)

    assert result["status"] == "ok"
    assert result["flash_match"] is True
    assert result["total_bytes_checked"] == 10
    assert result["total_mismatches"] == 0
    assert probe.calls == [
        (0x08000000, 3),
        (0x08000003, 3),
        (0x08000100, 3),
        (0x08000103, 1),
    ]
    assert result["sections"][1]["address"] == "0x20000000"
    assert result["sections"][1]["load_address"] == "0x8000100"
    assert result["sections"][1]["vma"] == "0x20000000"
    assert result["sections"][1]["classification"] == "flash_lma"
    assert result["sections"][2]["status"] == "skipped"
    assert result["sections"][2]["classification"] == "runtime_ram"


def test_elf_manager_get_section_data_includes_lma(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("McuBuddy.elf_manager.ELFFile", _FakeElfFile)

    elf_path = tmp_path / "fake.elf"
    elf_path.write_bytes(b"fake")
    manager = ElfManager()
    manager._path = elf_path

    sections = manager.get_section_data()

    assert sections[0] == {
        "name": ".text",
        "vma": 0x08000000,
        "lma": 0x08000000,
        "size": 0x120,
        "data": bytes(0x120),
    }
    assert sections[1]["vma"] == 0x20000000
    assert sections[1]["lma"] == 0x08001000


def test_compare_elf_to_flash_reports_flash_mismatch_explicitly() -> None:
    sections = [
        {
            "name": ".text",
            "vma": 0x08000000,
            "lma": 0x08000000,
            "size": 4,
            "data": b"good",
        }
    ]
    probe = _MemoryProbe({0x08000000: b"goof"})
    session = SimpleNamespace(
        elf=SimpleNamespace(is_loaded=True, get_section_data=lambda: sections),
        probe=probe,
        config=RuntimeConfig(),
    )

    result = compare_elf_to_flash(session)

    assert result["status"] == "ok"
    assert result["flash_match"] is False
    assert result["total_mismatches"] == 1
    assert result["sections"][0]["classification"] == "flash"
