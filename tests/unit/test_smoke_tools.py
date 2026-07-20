from McuBuddy.session import SessionState
from McuBuddy.tools.smoke import board_smoke_test, doctor, first_contact


class _Probe:
    def __init__(self) -> None:
        self.connected = False

    @classmethod
    def enumerate_probes(cls):
        return [{"unique_id": "abc", "description": "Demo CMSIS-DAP"}]

    def set_connect_hints(self, hints):
        self.hints = hints

    def set_pack_paths(self, pack_paths):
        self.pack_paths = pack_paths

    def connect(self, target, unique_id=None):
        self.connected = True
        return {"status": "ok", "target": target, "unique_id": unique_id}

    def halt(self):
        return {"status": "ok", "summary": "halted"}

    def get_state(self):
        return "halted"

    def read_core_registers(self):
        return {"pc": 0x08000100, "lr": 0x08000080, "sp": 0x20001000, "xpsr": 0x01000000}

    def read_fault_registers(self):
        return {"cfsr": 0, "hfsr": 0}

    def read_memory(self, address, size):
        return b"\x00\x10\x00\x20\x01\x01\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00"[:size]

    def disconnect(self):
        self.connected = False
        return {"status": "ok"}


class _Elf:
    is_loaded = True

    def load(self, path):
        return {"status": "ok", "path": path}

    def resolve_address(self, address):
        return {"symbol": "demo_symbol", "source": "main.c:1"}


def test_board_smoke_test_runs_generic_read_only_flow() -> None:
    session = SessionState()
    session.probe = _Probe()
    session.elf = _Elf()
    session.config.probe.target = "vendor_part"
    session.config.probe.unique_id = "abc"
    session.config.elf.path = r"d:\demo\app.axf"

    result = board_smoke_test(session, disconnect_after=True)

    assert result["status"] == "ok"
    assert [step["step"] for step in result["steps"]] == [
        "list_connected_probes",
        "elf_load",
        "connect_probe",
        "halt_target",
        "read_stopped_context",
        "read_vector_table",
        "probe_disconnect",
    ]
    vector_result = result["steps"][5]["result"]
    assert vector_result["decoded"]["initial_sp"] == "0x20001000"
    assert vector_result["decoded"]["reset_handler"] == "0x8000101"


def test_first_contact_configures_target_and_returns_next_steps() -> None:
    session = SessionState()
    session.probe = _Probe()
    session.elf = _Elf()

    result = first_contact(
        session,
        target="STM32L496VE",
        backend="pyocd",
        unique_id="abc",
        elf_path=r"d:\demo\app.axf",
        disconnect_after=True,
    )

    assert result["status"] == "ok"
    assert result["safety"]["level"] == "execution-changing"
    assert result["target_info"]["matched_target"] == "stm32l496vetx"
    assert session.config.probe.target == "stm32l496vetx"
    assert session.config.elf.path == r"d:\demo\app.axf"
    assert [item["kind"] for item in result["evidence"]] == [
        "target_info",
        "probe_config",
        "elf_config",
        "smoke_test",
    ]
    assert "read_stopped_context" in result["next_tools"]
    assert "diagnose" in result["next_tools"]


def test_doctor_reports_environment_and_probe_preflight() -> None:
    session = SessionState()
    session.probe = _Probe()
    session.config.probe.target = "STM32L496VE"
    session.config.probe.backend = "pyocd"
    session.config.elf.path = r"d:\demo\app.axf"

    result = doctor(session)

    assert result["status"] in {"ok", "warning"}
    assert result["safety"]["level"] == "read-only"
    kinds = [item["kind"] for item in result["evidence"]]
    assert kinds[0] == "runtime"
    assert "dependency" in kinds
    assert kinds[-3:] == ["probe_discovery", "target_info", "configuration"]
    assert "first_contact" in result["next_tools"]
    assert "board_smoke_test" in result["next_tools"]
