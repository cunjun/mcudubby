from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Literal


SkillTarget = Literal["codex", "claude", "both"]


def install_skill(
    *,
    target: SkillTarget = "codex",
    home: str | Path | None = None,
    source: str | Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    install_home = _resolve_home(home)
    source_path = _resolve_source(source)
    targets = _target_paths(target, install_home)

    if not (source_path / "SKILL.md").is_file():
        return {
            "status": "error",
            "summary": f"source is not a skill directory: {source_path}",
            "source": str(source_path),
        }

    entries = []
    if not dry_run and not force:
        existing = [path for _, path in targets if path.exists()]
        if existing:
            return {
                "status": "error",
                "summary": "skill destination already exists; rerun with --force to replace it.",
                "existing": [str(path) for path in existing],
            }

    for kind, dest in targets:
        existed = dest.exists()
        if dry_run:
            status = "would_replace" if existed else "would_install"
        else:
            if existed:
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_path, dest)
            status = "installed"
        entries.append({"kind": kind, "path": str(dest), "status": status})

    return {
        "status": "ok",
        "summary": f"Prepared mcubug skill installation for {target}.",
        "target": target,
        "home": str(install_home),
        "source": str(source_path),
        "dry_run": dry_run,
        "force": force,
        "entries": entries,
        "next_steps": _next_steps(target),
    }


def _resolve_home(home: str | Path | None) -> Path:
    if home is not None:
        return Path(home).expanduser().resolve()
    env_home = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    return Path(env_home).expanduser().resolve() if env_home else Path.home()


def _resolve_source(source: str | Path | None) -> Path:
    if source is not None:
        return Path(source).expanduser().resolve()
    repo_skill = Path(__file__).resolve().parents[2] / "skills" / "mcubug"
    return repo_skill.resolve()


def _target_paths(target: SkillTarget, home: Path) -> list[tuple[str, Path]]:
    targets: list[tuple[str, Path]] = []
    if target in ("codex", "both"):
        codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
        targets.append(("codex-skill", codex_home / "skills" / "mcubug"))
    if target in ("claude", "both"):
        claude_home = Path(os.environ.get("CLAUDE_HOME", home / ".claude"))
        targets.append(("claude-skill", claude_home / "skills" / "mcubug"))
    return targets


def _next_steps(target: SkillTarget) -> list[str]:
    steps = []
    if target in ("codex", "both"):
        steps.append("Use `$mcubug` in Codex after restarting the session.")
        steps.append(
            "Installing the skill does not register the McuBuddy MCP server; "
            "configure it with docs/windows-mcp-config-example.md, then restart Codex."
        )
    if target in ("claude", "both"):
        steps.append("Use the installed mcubug skill from Claude's local skills directory.")
    return steps
