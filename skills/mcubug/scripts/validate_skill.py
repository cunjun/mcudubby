"""Validate mcubug skill structure and local markdown links."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_REFERENCES = {
    "quickstart.md",
    "tool-reference.md",
    "support-matrix.md",
    "ai-playbook.md",
    "ai-examples.md",
    "generic-board-workflow.md",
    "board-validation-guide.md",
    "peripheral-actuator-debug-playbook.md",
}

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def iter_markdown_files(skill: Path):
    yield skill / "SKILL.md"
    references = skill / "references"
    if references.exists():
        yield from references.glob("*.md")


def validate_links(skill: Path) -> list[str]:
    errors: list[str] = []
    for path in iter_markdown_files(skill):
        if not path.exists():
            errors.append(f"missing markdown file: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group(1)
            if target.startswith(("http:", "https:", "mailto:", "#", "/")):
                continue
            target_path = (path.parent / target.split("#", 1)[0]).resolve()
            if not target_path.exists():
                errors.append(f"{path}: broken link {target}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "skill",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to the mcubug skill directory.",
    )
    args = parser.parse_args()

    skill = Path(args.skill).resolve()
    errors: list[str] = []

    if not (skill / "SKILL.md").exists():
        errors.append("missing SKILL.md")
    if not (skill / "agents" / "openai.yaml").exists():
        errors.append("missing agents/openai.yaml")

    references = skill / "references"
    present = {path.name for path in references.glob("*.md")} if references.exists() else set()
    for missing in sorted(REQUIRED_REFERENCES - present):
        errors.append(f"missing reference: references/{missing}")

    errors.extend(validate_links(skill))

    if errors:
        print("mcubug skill validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("mcubug skill validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
