import importlib

from McuBubby.session import SessionState
from McuBubby.tools.probe import rtos_switch_context


class _RecordingProbe:
    def __init__(self) -> None:
        self.writes: list[tuple[int, bytes]] = []

    def write_memory(self, address: int, data: bytes) -> None:
        self.writes.append((address, data))

    def read_core_registers(self) -> dict[str, int]:
        return {"sp": 0x20002000, "lr": 0xFFFFFFF9}


def test_rtos_switch_context_requires_confirmation_before_writing_target() -> None:
    session = SessionState()
    session.probe = _RecordingProbe()

    result = rtos_switch_context(session, task_name="worker")

    assert result["status"] == "error"
    assert result["safety"]["level"] == "state-changing"
    assert session.probe.writes == []


def test_rtos_switch_context_reports_unsupported_without_register_write_capability(
    monkeypatch,
) -> None:
    rtos_context_module = importlib.import_module("McuBubby.tools.probe.rtos_context")
    monkeypatch.setattr(
        rtos_context_module,
        "rtos_task_context",
        lambda session, task_name, task_name_len: {
            "status": "ok",
            "state": "blocked",
            "fpu_context": False,
            "registers": {
                "r0": 0,
                "r1": 1,
                "r2": 2,
                "r3": 3,
                "r12": 12,
                "lr": 0x08000101,
                "pc": 0x08000201,
                "xpsr": 0x21000000,
            },
        },
    )
    session = SessionState()
    session.probe = _RecordingProbe()

    result = rtos_switch_context(session, task_name="worker", confirm=True)

    assert result["status"] == "error"
    assert "core register writes" in result["summary"]
    assert session.probe.writes == []
