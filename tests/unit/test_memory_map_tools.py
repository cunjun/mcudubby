from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from McuBubby.elf_manager import ElfManager
from McuBubby.tools.probe import read_memory_map


class _FakeSection:
    def __init__(self, name: str, addr: int, size: int) -> None:
        self.name = name
        self._values = {
            "sh_addr": addr,
            "sh_size": size,
        }

    def __getitem__(self, key: str):
        return self._values[key]


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
    monkeypatch.setattr("McuBubby.elf_manager.ELFFile", _FakeElfFile)

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
