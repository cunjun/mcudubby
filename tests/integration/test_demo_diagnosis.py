from types import SimpleNamespace

from McuBuddy.demo.mock_session import MockSessionState
from McuBuddy.tools.diagnose import diagnose_hardfault, diagnose_startup_failure


def test_mock_startup_failure_contains_sensor_stage() -> None:
    session = MockSessionState()
    session.log.connect("COM-MOCK")
    session.probe.connect("stm32l4")
    session.elf.load("firmware.elf")

    result = diagnose_startup_failure(session, suspected_stage="sensor init")

    assert result["diagnosis_type"] == "startup_failure_with_fault"
    assert result["startup_context"]["suspected_stage"] == "sensor init"
    assert result["log_context"]["last_meaningful_line"] == "sensor init..."
    assert "suspected_root_causes" not in result
    assert "suggested_next_steps" not in result
    assert result["evidence"]


def test_mock_hardfault_resolves_handler_symbol() -> None:
    session = MockSessionState()
    session.log.connect("COM-MOCK")
    session.probe.connect("stm32l4")
    session.elf.load("firmware.elf")

    result = diagnose_hardfault(session, suspected_stage="sensor init")

    assert result["diagnosis_type"] == "hardfault_detected"
    assert result["symbol_context"]["pc_symbol"] == "HardFault_Handler"
    assert "suspected_root_causes" not in result
    assert "suggested_next_steps" not in result
    assert result["evidence"]


class _HealthyLogBackend:
    def connect(self, port: str, baudrate: int = 115200) -> dict:
        return {
            "status": "ok",
            "summary": f"Connected healthy mock UART on {port} at {baudrate} baud.",
        }

    def read_recent(self, line_count: int = 50) -> list[str]:
        return [
            "boot start",
            "clock init ok",
            "uart init ok",
            "sensor init...",
            "sensor init ok",
            "app loop running",
        ][-line_count:]


class _HealthyProbeBackend:
    def connect(self, target: str, unique_id: str | None = None) -> dict:
        return {"status": "ok", "summary": f"Connected healthy mock target {target}."}

    def halt(self) -> dict:
        return {"status": "ok", "summary": "Healthy mock target halted."}

    def read_core_registers(self) -> dict[str, int]:
        return {
            "pc": 0x0800237E,
            "lr": 0x08002351,
            "sp": 0x2000079C,
            "xpsr": 0x81000000,
        }

    def read_fault_registers(self) -> dict[str, int]:
        return {
            "cfsr": 0x0,
            "hfsr": 0x0,
            "mmfar": 0xE000EDF8,
            "bfar": 0xE000EDF8,
            "shcsr": 0x0,
        }


class _HealthyElfManager:
    is_loaded = True

    def load(self, path: str) -> dict:
        return {"status": "ok", "summary": f"Loaded healthy mock ELF from {path}."}

    def resolve_address(self, address: int) -> dict:
        mapping = {
            0x0800237E: {"symbol": "delay_us", "source": "app_main.c:123"},
            0x08002351: {"symbol": "delay_ms", "source": "delay.c:45"},
        }
        return mapping.get(address, {"symbol": None, "source": None})


class _HealthySession:
    def __init__(self) -> None:
        self.log = _HealthyLogBackend()
        self.probe = _HealthyProbeBackend()
        self.elf = _HealthyElfManager()
        self.config = SimpleNamespace(
            probe=SimpleNamespace(backend="jlink"),
            log=SimpleNamespace(backend="uart"),
        )


def test_startup_success_is_reported_when_logs_continue_normally() -> None:
    session = _HealthySession()

    result = diagnose_startup_failure(session, suspected_stage="sensor init")

    assert result["diagnosis_type"] == "startup_completed_normally"
    assert result["confidence"] == "high"
    assert result["startup_context"]["progress_interrupted"] is False
    assert result["log_context"]["log_stopped_abruptly"] is False
    assert result["fault"]["fault_detected"] is False
    assert result["log_context"]["last_meaningful_line"] == "app loop running"
    assert "suspected_root_causes" not in result
    assert "suggested_next_steps" not in result
    assert result["symbol_context"]["source"] == "app_main.c:123"


def test_diagnosis_raw_refs_report_configured_probe_backend() -> None:
    session = _HealthySession()

    result = diagnose_startup_failure(session, suspected_stage="sensor init")

    assert result["raw_refs"]["probe_backend"] == "jlink"
    assert result["raw_refs"]["log_backend"] == "uart"
