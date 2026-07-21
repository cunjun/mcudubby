"""Install the repository mcubug skill into a local AI assistant skills directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from McuBuddy.skill_installer import install_skill  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=["codex", "claude", "both", "cc"],
        default="codex",
        help="Assistant skill directory to install into. Defaults to codex. 'cc' is an alias for claude.",
    )
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to the source mcubug skill directory.",
    )
    parser.add_argument(
        "--home",
        default=None,
        help="Home directory used to resolve ~/.codex or ~/.claude.",
    )
    parser.add_argument(
        "--overwrite",
        "--force",
        dest="force",
        action="store_true",
        help="Replace an existing mcubug skill at the destination.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report.")
    args = parser.parse_args()

    target = "claude" if args.target == "cc" else args.target
    report = install_skill(
        target=target,
        home=args.home,
        source=Path(args.source).resolve(),
        dry_run=args.dry_run,
        force=args.force,
    )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(report["summary"])
        for entry in report.get("entries", []):
            print(f"{entry['kind']}: {entry['path']} ({entry['status']})")
        for step in report.get("next_steps", []):
            print(f"- {step}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
