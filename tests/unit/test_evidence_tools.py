from __future__ import annotations

from McuBuddy.session import SessionState
from McuBuddy.tools.evidence import (
    collect_crash_evidence,
    collect_peripheral_evidence,
    collect_rtos_evidence,
)


class _DisconnectedProbe:
    def halt(self) -> dict:
        raise RuntimeError("probe target is not connected")

    def read_core_registers(self) -> dict[str, int]:
        raise RuntimeError("probe target is not connected")

    def read_fault_registers(self) -> dict[str, int]:
        raise RuntimeError("probe target is not connected")

    def read_memory(self, address: int, size: int) -> bytes:
        raise RuntimeError("probe target is not connected")

    def get_state(self) -> str:
        raise RuntimeError("probe target is not connected")


class _ConnectedProbe:
    def halt(self) -> dict:
        return {"status": "ok", "summary": "halted"}

    def read_core_registers(self) -> dict[str, int]:
        return {
            "pc": 0x08000100,
            "lr": 0xFFFFFFF9,
            "sp": 0x20001000,
            "xpsr": 0x01000000,
        }

    def read_fault_registers(self) -> dict[str, int]:
        return {"cfsr": 0, "hfsr": 0}

    def read_memory(self, address: int, size: int) -> bytes:
        return bytes(range(size))

    def get_state(self) -> str:
        return "halted"


class _Log:
    def read_recent(self, line_count: int = 50) -> list[str]:
        return ["boot", "fault"]


class _Svd:
    is_loaded = True

    def read_peripheral_state(self, peripheral_name: str, probe) -> dict:
        if peripheral_name == "GPIOB":
            raise RuntimeError("register read failed")
        return {"status": "ok", "peripheral": peripheral_name}


class _Elf:
    is_loaded = False


def test_crash_evidence_reports_missing_probe_prerequisite() -> None:
    session = SessionState(probe=_DisconnectedProbe())

    result = collect_crash_evidence(session)

    assert result["status"] == "error"
    assert result["evidence"][0]["kind"] == "halt"
    assert result["evidence"][0]["status"] == "unavailable"
    assert "root cause" not in result["summary"].lower()


def test_crash_evidence_collects_context_and_stack_snapshot() -> None:
    session = SessionState(probe=_ConnectedProbe(), log=_Log(), elf=_Elf())

    result = collect_crash_evidence(session, stack_snapshot_bytes=4)

    assert result["status"] == "ok"
    assert {item["kind"] for item in result["evidence"]} == {
        "halt",
        "stopped_context",
        "stack_snapshot",
    }
    assert result["evidence"][2]["result"]["data_hex"] == "00 01 02 03"


def test_peripheral_evidence_allows_partial_success() -> None:
    session = SessionState(probe=_ConnectedProbe(), svd=_Svd())

    result = collect_peripheral_evidence(session, peripheral="USART2")

    assert result["status"] == "partial"
    assert result["peripheral"] == "USART2"
    assert any(item["status"] == "unavailable" for item in result["evidence"])


def test_rtos_evidence_reports_unavailable_without_fake_diagnosis() -> None:
    session = SessionState(probe=_ConnectedProbe(), elf=_Elf())

    result = collect_rtos_evidence(session)

    assert result["status"] == "error"
    assert result["next_tools"] == ["rtos_task_context", "read_stack_usage"]
    assert "most likely" not in result["summary"].lower()
