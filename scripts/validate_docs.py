"""Validate stable documentation contracts for the repository."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
IDENTIFIER_RE = re.compile(r"\b[a-z][a-z0-9_]+\b")
PROFILE_START_RE = re.compile(r"<!--\s*mcubuddy-profile:\s*(core|full)\s*-->")
PROFILE_END = "<!-- /mcubuddy-profile -->"
STALE_REFERENCES = ("PROGRESS.md", "README_CN.md")
MACHINE_PATH_PATTERNS = (
    re.compile(r"file:///", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\work_code\\", re.IGNORECASE),
)
README_REQUIRED_TOKENS = {
    "README.md": (
        "core",
        "MCUBUDDY_TOOL_PROFILE=full",
        "docs/quickstart.md",
        "docs/tool-reference.md",
        "execution-changing",
    ),
    "README_zh.md": (
        "core",
        "MCUBUDDY_TOOL_PROFILE=full",
        "docs/quickstart.md",
        "docs/tool-reference.md",
        "执行状态变化",
    ),
}
UPSTREAM_COPYRIGHT = "Copyright (c) 2026 SolarWang233"
UPSTREAM_URL = "https://github.com/SolarWang233/mcudbg"
UPSTREAM_URL_FILES = ("NOTICE", "README.md", "README_zh.md", "pyproject.toml")


def validate_repository(repo: Path) -> list[str]:
    repo = repo.resolve()
    errors: list[str] = []
    for path in _iter_markdown_files(repo):
        errors.extend(_validate_links(repo, path))

    known_tools, core_tools, tool_errors = _load_tool_names(repo)
    errors.extend(tool_errors)
    for path in _iter_current_docs(repo):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(repo).as_posix()
        errors.extend(_validate_stale_references(relative, text))
        errors.extend(_validate_profile_regions(relative, text, known_tools, core_tools))

    errors.extend(_validate_readmes(repo))
    errors.extend(_validate_upstream_license(repo))
    errors.extend(_validate_upstream_urls(repo))
    return sorted(errors)


def _iter_markdown_files(repo: Path):
    for path in repo.rglob("*.md"):
        relative_parts = path.relative_to(repo).parts
        if any(
            part in {".git", ".venv", ".uv-cache", "__pycache__"}
            for part in relative_parts
        ):
            continue
        if relative_parts[:3] == ("skills", "mcubug", "references"):
            continue
        yield path


def _iter_current_docs(repo: Path):
    for name in ("README.md", "README_zh.md"):
        path = repo / name
        if path.exists():
            yield path

    docs = repo / "docs"
    if docs.exists():
        for path in docs.rglob("*.md"):
            relative_parts = path.relative_to(docs).parts
            if relative_parts and relative_parts[0] in {"plans", "archive", "releases"}:
                continue
            yield path

    skill = repo / "skills" / "mcubug" / "SKILL.md"
    if skill.exists():
        yield skill


def _validate_links(repo: Path, path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(repo).as_posix()
    for match in LINK_RE.finditer(text):
        raw_target = match.group(1).strip()
        if raw_target.startswith("<") and ">" in raw_target:
            target = raw_target[1 : raw_target.index(">")]
        else:
            target = raw_target.split(maxsplit=1)[0]
        if target.startswith(("http:", "https:", "mailto:", "#", "/")):
            continue
        target_without_anchor = target.split("#", 1)[0]
        if target_without_anchor and not (path.parent / target_without_anchor).resolve().exists():
            errors.append(f"{relative}: broken link '{target}'")
    return errors


def _validate_stale_references(relative: str, text: str) -> list[str]:
    errors = [
        f"{relative}: stale reference '{token}'"
        for token in STALE_REFERENCES
        if token in text
    ]
    for pattern in MACHINE_PATH_PATTERNS:
        match = pattern.search(text)
        if match:
            errors.append(f"{relative}: machine-specific path '{match.group(0)}'")
    return errors


def _validate_profile_regions(
    relative: str,
    text: str,
    known_tools: set[str],
    core_tools: set[str],
) -> list[str]:
    errors: list[str] = []
    start_count = len(PROFILE_START_RE.findall(text))
    end_count = text.count(PROFILE_END)
    if end_count > start_count:
        errors.append(f"{relative}: unmatched {PROFILE_END}")
    cursor = 0
    while match := PROFILE_START_RE.search(text, cursor):
        profile = match.group(1)
        end = text.find(PROFILE_END, match.end())
        if end == -1:
            errors.append(f"{relative}: missing {PROFILE_END}")
            break
        if PROFILE_START_RE.search(text, match.end(), end):
            errors.append(f"{relative}: nested mcubuddy profile regions are not allowed")
        region = text[match.end() : end]
        if profile == "core":
            used_tools = set(IDENTIFIER_RE.findall(region)) & known_tools
            for tool_name in sorted(used_tools - core_tools):
                errors.append(
                    f"{relative}: core region uses full-only tool '{tool_name}'"
                )
        cursor = end + len(PROFILE_END)
    return errors


def _load_tool_names(repo: Path) -> tuple[set[str], set[str], list[str]]:
    profiles_path = repo / "src" / "McuBuddy" / "tool_profiles.py"
    safety_path = repo / "src" / "McuBuddy" / "tool_safety.py"
    core_tools = _read_constant_names(profiles_path, "CORE_TOOL_NAMES")
    policies = _read_constant_names(safety_path, "TOOL_POLICIES")
    concurrent = _read_constant_names(safety_path, "CONCURRENT_TOOLS")
    errors: list[str] = []
    if not core_tools:
        errors.append("src/McuBuddy/tool_profiles.py: unable to load CORE_TOOL_NAMES")
    if not policies:
        errors.append("src/McuBuddy/tool_safety.py: unable to load TOOL_POLICIES")
    return core_tools | policies | concurrent, core_tools, errors


def _read_constant_names(path: Path, constant_name: str) -> set[str]:
    if not path.exists():
        return set()
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in module.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == constant_name
            for target in targets
        ):
            continue
        value = node.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            if value.func.id == "frozenset" and value.args:
                value = value.args[0]
        if isinstance(value, ast.Dict):
            return {
                key.value
                for key in value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
        if isinstance(value, (ast.Set, ast.List, ast.Tuple)):
            return {
                item.value
                for item in value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            }
    return set()


def _validate_readmes(repo: Path) -> list[str]:
    errors: list[str] = []
    for name, required_tokens in README_REQUIRED_TOKENS.items():
        path = repo / name
        if not path.exists():
            errors.append(f"{name}: missing file")
            continue
        text = path.read_text(encoding="utf-8")
        for token in required_tokens:
            if token not in text:
                errors.append(f"{name}: missing critical token '{token}'")
    return errors


def _validate_upstream_license(repo: Path) -> list[str]:
    path = repo / "LICENSE"
    if not path.exists() or UPSTREAM_COPYRIGHT not in path.read_text(encoding="utf-8"):
        return ["LICENSE: missing upstream copyright"]
    return []


def _validate_upstream_urls(repo: Path) -> list[str]:
    errors: list[str] = []
    for name in UPSTREAM_URL_FILES:
        path = repo / name
        if not path.exists() or UPSTREAM_URL not in path.read_text(encoding="utf-8"):
            errors.append(f"{name}: missing upstream URL")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root to validate.",
    )
    args = parser.parse_args()
    errors = validate_repository(args.repo)
    if errors:
        print("documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("documentation validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
