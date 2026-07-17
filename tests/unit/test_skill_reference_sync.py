from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_SCRIPT = REPO_ROOT / "skills" / "mcubug" / "scripts" / "sync_references.py"


def test_reference_sync_check_detects_drift_without_modifying_files(tmp_path: Path) -> None:
    skill_dir = tmp_path / "mcubug"
    references = skill_dir / "references"
    references.mkdir(parents=True)
    stale_reference = references / "quickstart.md"
    stale_reference.write_text("stale", encoding="utf-8")

    result = _run_sync(skill_dir, "--check")

    assert result.returncode == 1
    assert stale_reference.read_text(encoding="utf-8") == "stale"

    assert _run_sync(skill_dir).returncode == 0
    assert _run_sync(skill_dir, "--check").returncode == 0


def _run_sync(skill_dir: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SYNC_SCRIPT),
            "--repo",
            str(REPO_ROOT),
            "--skill",
            str(skill_dir),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
