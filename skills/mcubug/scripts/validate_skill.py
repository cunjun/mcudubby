"""Validate mcubug skill structure and local markdown links."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_REFERENCES = {
    "quickstart.md",
    "windows-mcp-config-example.md",
    "tool-reference.md",
    "support-matrix.md",
    "ai-playbook.md",
    "ai-examples.md",
    "generic-board-workflow.md",
    "board-validation-guide.md",
    "peripheral-actuator-debug-playbook.md",
}

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<content>.*?)\n---(?:\s*\n|\Z)", re.DOTALL)
SKILL_NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


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


def validate_frontmatter(text: str, *, expected_name: str) -> list[str]:
    match = FRONTMATTER_RE.match(text)
    if match is None:
        return ["SKILL.md is missing YAML frontmatter"]

    content = match.group("content")
    if len(content) > 1024:
        return ["frontmatter exceeds 1024 characters"]

    fields: dict[str, str] = {}
    errors: list[str] = []
    for line in content.splitlines():
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            errors.append(f"invalid frontmatter line: {line}")
            continue
        fields[key.strip()] = value.strip().strip('"').strip("'")

    unknown = sorted(set(fields) - {"name", "description"})
    if unknown:
        errors.append(f"unsupported frontmatter fields: {', '.join(unknown)}")

    name = fields.get("name", "")
    if name != expected_name:
        errors.append(f"name must match skill directory: {expected_name}")
    if name and SKILL_NAME_RE.fullmatch(name) is None:
        errors.append("name must use lowercase letters, digits, and hyphens")

    description = fields.get("description", "")
    if not description.startswith("Use when "):
        errors.append("description must start with 'Use when '")
    if len(description) > 500:
        errors.append("description exceeds 500 characters")
    return errors


def validate_body(text: str) -> list[str]:
    if len(text.split()) > 600:
        return ["SKILL.md exceeds 600 words"]
    return []


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
    else:
        skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
        errors.extend(validate_frontmatter(skill_text, expected_name=skill.name))
        errors.extend(validate_body(skill_text))
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
