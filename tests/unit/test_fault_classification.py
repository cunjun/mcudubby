from mcudubby.tools.diagnose import _classify_fault, _infer_stage_from_logs


def test_precise_data_bus_fault_classification() -> None:
    result = _classify_fault({"cfsr": 0x00008200, "hfsr": 0})
    assert result == "precise_data_bus_error"


def test_instruction_access_violation_classification() -> None:
    result = _classify_fault({"cfsr": 0x00000001, "hfsr": 0x40000000})
    assert result == "instruction_access_violation"


def test_forced_hardfault_classification() -> None:
    result = _classify_fault({"cfsr": 0, "hfsr": 0x40000000})
    assert result == "forced_hardfault"


def test_infer_stage_from_sensor_log() -> None:
    result = _infer_stage_from_logs("sensor init...")
    assert result == "sensor initialization"
