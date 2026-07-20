from McuBubby.validation_records import list_validation_records


def test_validation_records_are_machine_readable() -> None:
    result = list_validation_records()

    assert result["status"] == "ok"
    assert result["count"] >= 2
    ids = {record["id"] for record in result["records"]}
    assert "stm32l496vetx-pyocd-stlink" in ids
    assert "stm32f103c8-jlink" in ids

    stm32l4 = next(record for record in result["records"] if record["id"] == "stm32l496vetx-pyocd-stlink")
    assert stm32l4["backend"] == "pyocd"
    assert "rtos_task_context" in stm32l4["validated_tools"]
