"""Sync mcubug skill references from this McuBuddy checkout."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REFERENCE_MAP = {
    "docs/quickstart.md": "quickstart.md",
    "docs/tool-reference.md": "tool-reference.md",
    "docs/support-matrix.md": "support-matrix.md",
    "docs/ai-playbook.md": "ai-playbook.md",
    "docs/ai-examples.md": "ai-examples.md",
    "docs/generic-board-workflow.md": "generic-board-workflow.md",
    "docs/board-validation-guide.md": "board-validation-guide.md",
    "docs/peripheral-actuator-debug-playbook.md": "peripheral-actuator-debug-playbook.md",
}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=str(default_repo_root()),
        help="Path to the McuBuddy repository checkout.",
    )
    parser.add_argument(
        "--skill",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to the mcubug skill directory.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for missing or stale references without modifying files.",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    skill = Path(args.skill).resolve()
    references = skill / "references"
    if not args.check:
        references.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []
    stale: list[str] = []
    for source_name, dest_name in REFERENCE_MAP.items():
        source = repo / source_name
        dest = references / dest_name
        if not source.exists():
            missing.append(str(source))
            continue
        if args.check:
            if not dest.exists() or source.read_bytes() != dest.read_bytes():
                stale.append(f"{source_name} -> references/{dest_name}")
            continue
        shutil.copyfile(source, dest)
        print(f"synced {source_name} -> references/{dest_name}")

    if missing:
        print("missing source files:")
        for item in missing:
            print(f"- {item}")
    if stale:
        print("stale or missing references:")
        for item in stale:
            print(f"- {item}")

    return 1 if missing or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
