from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).parents[2]
VALIDATOR_PATH = ROOT / "skills" / "mcubug" / "scripts" / "validate_skill.py"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mcubug_skill_validator", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frontmatter_validation_rejects_non_trigger_description() -> None:
    validator = _load_validator()
    text = "---\nname: mcubug\ndescription: Debug MCU boards\n---\n\n# mcubug\n"

    errors = validator.validate_frontmatter(text, expected_name="mcubug")

    assert "description must start with 'Use when '" in errors


def test_frontmatter_validation_accepts_current_skill() -> None:
    validator = _load_validator()
    text = (ROOT / "skills" / "mcubug" / "SKILL.md").read_text(encoding="utf-8")

    assert validator.validate_frontmatter(text, expected_name="mcubug") == []


def test_skill_body_validation_enforces_concise_main_file() -> None:
    validator = _load_validator()
    text = "---\nname: mcubug\ndescription: Use when debugging boards\n---\n\n" + (
        "word " * 601
    )

    assert validator.validate_body(text) == ["SKILL.md exceeds 600 words"]
