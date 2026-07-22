from __future__ import annotations

from pathlib import Path
import re

from McuBuddy.tool_profiles import CORE_TOOL_NAMES


ROOT = Path(__file__).parents[2]
SKILL_PATH = ROOT / "skills" / "mcubug" / "SKILL.md"
TOOL_CALL_RE = re.compile(r"`([a-z][a-z0-9_]*)\([^`]*\)`")


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


def test_skill_preflights_runtime_before_probe_configuration() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    assert "`doctor()`" in skill
    assert "`first_contact()`" in skill
    assert skill.index("`doctor()`") < skill.index("`configure_probe(...)")
    assert skill.index("`first_contact()`") < skill.index("`configure_probe(...)")


def test_skill_marks_every_hidden_tool_call_as_full_only() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    unmarked: list[str] = []

    for line_number, line in enumerate(skill.splitlines(), start=1):
        for tool_name in TOOL_CALL_RE.findall(line):
            if tool_name not in CORE_TOOL_NAMES and "full-only" not in line.lower():
                unmarked.append(f"{line_number}:{tool_name}")

    assert unmarked == []


def test_skill_body_stays_concise() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    assert len(skill.split()) <= 600


def test_quickstart_documents_management_and_rtt_safety_preflight() -> None:
    quickstart = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")

    assert "McuBuddy doctor --json" in quickstart
    assert "McuBuddy config show --json" in quickstart
    assert "MCUBUDDY_MAX_RTT_SCAN_SIZE" in quickstart


def test_session_workflows_start_with_core_preflight() -> None:
    for relative_path in [
        "docs/ai-playbook.md",
        "docs/ai-examples.md",
        "docs/generic-board-workflow.md",
        "docs/board-validation-guide.md",
    ]:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "doctor()" in text, relative_path
        assert "first_contact()" in text, relative_path
        assert text.index("doctor()") < text.index("configure_probe(")
        assert text.index("first_contact()") < text.index("configure_probe(")


def test_windows_setup_runs_doctor_before_hardware_access() -> None:
    windows = (ROOT / "docs" / "windows-mcp-config-example.md").read_text(
        encoding="utf-8"
    )

    assert "McuBuddy.exe' doctor --json" in windows
    assert windows.index("doctor --json") < windows.index("configure_probe(")
