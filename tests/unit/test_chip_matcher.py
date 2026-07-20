from types import SimpleNamespace

from McuBubby.chip_matcher import match_chip_name
from McuBubby.device_patch_manager import list_supported_targets, resolve_device_patch
from McuBubby.tools.probe import connect_probe


def test_match_chip_name_passes_through_unknown_name() -> None:
    result = match_chip_name("stm32-custom-board", backend="pyocd")

    assert result["status"] == "ok"
    assert result["matched_target"] == "stm32-custom-board"
    assert result["confidence"] == "pass_through"


def test_match_chip_name_resolves_known_pyocd_alias() -> None:
    result = match_chip_name("STM32F103C8T6", backend="pyocd")

    assert result["status"] == "ok"
    assert result["matched_target"] == "stm32f103c8"
    assert result["confidence"] == "high"


def test_match_chip_name_resolves_py32_pyocd_alias() -> None:
    result = match_chip_name("PY32F030X8", backend="CMSIS-DAP")

    assert result["status"] == "ok"
    assert result["backend"] == "pyocd"
    assert result["matched_target"] == "py32f030x8"
    assert result["confidence"] == "high"


def test_match_chip_name_normalizes_backend_alias() -> None:
    result = match_chip_name("STM32F103C8T6", backend="J-Link")

    assert result["status"] == "ok"
    assert result["backend"] == "jlink"
    assert result["matched_target"] == "STM32F103C8"


def test_match_chip_name_reports_unknown_backend() -> None:
    result = match_chip_name("STM32F103C8T6", backend="blackmagic")

    assert result["status"] == "error"
    assert "Unsupported probe backend" in result["summary"]
    assert "pyocd" in result["supported_backends"]


def test_connect_probe_applies_backend_specific_match() -> None:
    captured: dict[str, str | None] = {}
    captured_hints: dict[str, object] = {}

    def _connect(*, target: str, unique_id: str | None = None) -> dict:
        captured["target"] = target
        captured["unique_id"] = unique_id
        return {"status": "ok", "summary": f"Connected to {target}."}

    def _set_connect_hints(hints: dict) -> None:
        captured_hints.update(hints)

    def _get_state() -> str:
        return "running"

    session = SimpleNamespace(
        config=SimpleNamespace(probe=SimpleNamespace(backend="jlink")),
        probe=SimpleNamespace(
            connect=_connect,
            set_connect_hints=_set_connect_hints,
            get_state=_get_state,
        ),
    )

    result = connect_probe(session, target="STM32F103C8T6", unique_id="240710115")

    assert captured["target"] == "STM32F103C8"
    assert captured["unique_id"] == "240710115"
    assert result["target_match"]["matched_target"] == "STM32F103C8"
    assert result["target_patch"]["patch_applied"] is True
    assert captured_hints["speeds"] == [4000, 1000, 400, "auto"]
    assert "halt" not in result["post_connect"]
    assert result["post_connect"]["state"] == "running"


def test_resolve_device_patch_returns_connect_hints() -> None:
    result = resolve_device_patch("STM32L496VE", backend="pyocd")

    assert result["status"] == "ok"
    assert result["matched_target"] == "stm32l496vetx"
    assert result["patch_applied"] is True
    assert result["connect_hints"]["attempts"][0]["frequency"] == 4000000
    assert result["post_connect_checks"]["read_state"] is True
    assert "halt" not in result["post_connect_checks"]
    assert result["recovery_guidance"]


def test_resolve_device_patch_returns_py32_cmsis_dap_profile() -> None:
    result = resolve_device_patch("PY32F030X8", backend="pyocd")

    assert result["status"] == "ok"
    assert result["matched_target"] == "py32f030x8"
    assert result["patch_applied"] is True
    assert result["support_tier"] == "validated"
    assert result["recommended_probe"] == "CMSIS-DAP"
    assert result["connect_hints"]["attempts"][0] == {
        "frequency": 100000,
        "connect_mode": "attach",
    }
    assert "vector_table" in result["validated_capabilities"]


def test_resolve_device_patch_includes_warnings_for_f103() -> None:
    result = resolve_device_patch("STM32F103C8T6", backend="jlink")

    assert result["status"] == "ok"
    assert result["patch_applied"] is True
    assert "PB3" in result["warnings"][0]


def test_resolve_device_patch_reports_validation_metadata() -> None:
    result = resolve_device_patch("STM32L496VE", backend="pyocd")

    assert result["status"] == "ok"
    assert result["support_tier"] == "validated"
    assert result["recommended_probe"] == "ST-Link"
    assert "rtos" in result["validated_capabilities"]
    assert result["validated_hardware"][0]["board"] == "ATK_PICTURE"


def test_resolve_device_patch_returns_deep_copies() -> None:
    first = resolve_device_patch("STM32L496VE", backend="pyocd")
    first["validated_hardware"][0]["board"] = "BROKEN"
    first["connect_hints"]["attempts"][0]["frequency"] = 123

    second = resolve_device_patch("STM32L496VE", backend="pyocd")

    assert second["validated_hardware"][0]["board"] == "ATK_PICTURE"
    assert second["connect_hints"]["attempts"][0]["frequency"] == 4000000


def test_list_supported_targets_returns_profiles() -> None:
    result = list_supported_targets(backend="jlink")

    assert result["status"] == "ok"
    assert result["backend"] == "jlink"
    assert any(target["target"] == "STM32F103C8" for target in result["targets"])


def test_list_supported_targets_normalizes_backend_alias() -> None:
    result = list_supported_targets(backend="ST-Link")

    assert result["status"] == "ok"
    assert result["backend"] == "pyocd"
    assert any(target["target"] == "py32f030x8" for target in result["targets"])
    assert any(target["target"] == "stm32l496vetx" for target in result["targets"])


def test_list_supported_targets_reports_unknown_backend() -> None:
    result = list_supported_targets(backend="blackmagic")

    assert result["status"] == "error"
    assert "Unsupported probe backend" in result["summary"]
