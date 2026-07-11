"""Install the repository mcubug skill into a local AI assistant skills directory."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def default_codex_skill_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "skills"
    return Path.home() / ".codex" / "skills"


def default_cc_skill_root() -> Path:
    claude_home = os.environ.get("CLAUDE_HOME")
    if claude_home:
        return Path(claude_home) / "skills"
    return Path.home() / ".claude" / "skills"


def default_skill_root(target: str) -> Path:
    if target == "cc":
        return default_cc_skill_root()
    return default_codex_skill_root()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=["codex", "cc"],
        default="codex",
        help="Assistant skill directory to install into. Defaults to codex.",
    )
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to the source mcubug skill directory.",
    )
    parser.add_argument(
        "--dest-root",
        default=None,
        help=(
            "Destination skills directory. Defaults to CODEX_HOME/skills or ~/.codex/skills "
            "for Codex, and CLAUDE_HOME/skills or ~/.claude/skills for CC."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing mcubug skill at the destination.",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    dest_root = Path(args.dest_root).resolve() if args.dest_root else default_skill_root(args.target)
    dest = dest_root / "mcubug"

    if not (source / "SKILL.md").exists():
        print(f"source is not a skill directory: {source}")
        return 1

    if dest.exists():
        if not args.overwrite:
            print(f"destination already exists: {dest}")
            print("rerun with --overwrite to replace it")
            return 1
        shutil.rmtree(dest)

    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)
    print(f"installed mcubug skill to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
