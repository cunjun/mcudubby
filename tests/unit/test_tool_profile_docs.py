from __future__ import annotations

from pathlib import Path

from McuBuddy.tool_profiles import CORE_TOOL_NAMES


ROOT = Path(__file__).parents[2]


def test_evaluation_scenarios_are_parseable_and_complete() -> None:
    text = (ROOT / "tests" / "evaluation" / "gpt5p6_scenarios.yaml").read_text(
        encoding="utf-8"
    )

    for scenario_id in [
        "board-bring-up",
        "hardfault-evidence",
        "uart-no-output",
        "freertos-stall",
        "keil-build-flash-verify",
    ]:
        assert f"id: {scenario_id}" in text
    assert text.count("baseline:") == 5
    assert "executed: false" in text


def test_quickstart_documents_core_and_full_profiles() -> None:
    quickstart = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")

    assert "MCUBUDDY_TOOL_PROFILE" in quickstart
    assert "core" in quickstart
    assert "full" in quickstart


def test_documented_core_tools_match_code_allowlist() -> None:
    reference = (ROOT / "docs" / "tool-reference.md").read_text(encoding="utf-8")

    missing = {name for name in CORE_TOOL_NAMES if name not in reference}

    assert missing == set()
