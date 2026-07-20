from __future__ import annotations

from McuBubby.tools.probe import addr_to_source
from McuBubby.tools.probe import source_step


class _FakeElf:
    is_loaded = True

    def __init__(self) -> None:
        self._lines = {
            0x08000100: {"file": "main.c", "line": 10},
            0x08000102: {"file": "main.c", "line": 10},
            0x08000104: {"file": "main.c", "line": 11},
            0x08000106: {"file": "main.c", "line": 11},
        }
        self._resolved = {
            0x08000100: {"address": "0x8000100", "symbol": "foo", "source": "main.c:10"},
            0x08000102: {"address": "0x8000102", "symbol": "foo", "source": "main.c:10"},
            0x08000104: {"address": "0x8000104", "symbol": "foo", "source": "main.c:11"},
            0x08000106: {"address": "0x8000106", "symbol": "foo", "source": "main.c:11"},
        }

    def addr_to_source(self, address: int) -> dict:
        return self._lines.get(address, {"file": None, "line": None})

    def resolve_address(self, address: int) -> dict:
        return self._resolved.get(
            address, {"address": hex(address), "symbol": None, "source": None}
        )


class _NoDwarfElf:
    is_loaded = True

    def addr_to_source(self, address: int) -> dict:
        return {"file": None, "line": None}

    def resolve_address(self, address: int) -> dict:
        return {"address": hex(address), "symbol": "fallback_symbol", "source": None}


class _FakeProbe:
    def __init__(self, pcs: list[int]) -> None:
        self._pcs = pcs
        self._index = 0

    def read_core_registers(self) -> dict[str, int]:
        return {
            "pc": self._pcs[self._index],
            "lr": 0x08000000,
            "sp": 0x20000000,
            "xpsr": 0x01000000,
        }

    def step(self) -> dict:
        if self._index < len(self._pcs) - 1:
            self._index += 1
        return {
            "status": "ok",
            "summary": "Stepped one instruction.",
            "pc": hex(self._pcs[self._index]),
        }


class _Session:
    def __init__(self, elf, probe) -> None:
        self.elf = elf
        self.probe = probe


def test_addr_to_source_returns_line_and_symbol() -> None:
    session = _Session(_FakeElf(), _FakeProbe([0x08000100]))

    result = addr_to_source(session, 0x08000104)

    assert result["status"] == "ok"
    assert result["file"] == "main.c"
    assert result["line"] == 11
    assert result["source"] == "main.c:11"
    assert result["symbol"] == "foo"


def test_source_step_advances_until_source_line_changes() -> None:
    session = _Session(_FakeElf(), _FakeProbe([0x08000100, 0x08000102, 0x08000104]))

    result = source_step(session)

    assert result["status"] == "ok"
    assert result["pc"] == "0x8000104"
    assert result["file"] == "main.c"
    assert result["line"] == 11
    assert result["source"] == "main.c:11"
    assert result["instructions_executed"] == 2


def test_source_step_falls_back_to_instruction_step_without_dwarf() -> None:
    session = _Session(_NoDwarfElf(), _FakeProbe([0x08000100, 0x08000102]))

    result = source_step(session)

    assert result["status"] == "ok"
    assert result["pc"] == "0x8000102"
    assert result["symbol"] == "fallback_symbol"
    assert result["source"] is None
