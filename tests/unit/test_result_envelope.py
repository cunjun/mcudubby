from McuBubby.result import make_result, safety_info


def test_make_result_adds_standard_ai_fields() -> None:
    result = make_result(
        status="ok",
        summary="Ready.",
        evidence=[{"kind": "probe", "result": {"status": "ok"}}],
        next_tools=["read_stopped_context"],
        safety=safety_info("read-only", "No writes."),
        payload={"target": "stm32f103c8"},
    )

    assert result["status"] == "ok"
    assert result["summary"] == "Ready."
    assert result["evidence"][0]["kind"] == "probe"
    assert result["next_tools"] == ["read_stopped_context"]
    assert result["safety"]["level"] == "read-only"
    assert result["target"] == "stm32f103c8"


def test_make_result_defaults_optional_fields() -> None:
    result = make_result(status="error", summary="Missing target.")

    assert result["evidence"] == []
    assert result["next_tools"] == []
    assert result["safety"]["level"] == "unknown"


def test_make_result_payload_cannot_override_standard_fields() -> None:
    result = make_result(
        status="ok",
        summary="Ready.",
        safety=safety_info("read-only"),
        payload={
            "status": "error",
            "summary": "Overwritten.",
            "safety": safety_info("persistent-destructive"),
            "target": "stm32f103c8",
        },
    )

    assert result["status"] == "ok"
    assert result["summary"] == "Ready."
    assert result["safety"]["level"] == "read-only"
    assert result["target"] == "stm32f103c8"
