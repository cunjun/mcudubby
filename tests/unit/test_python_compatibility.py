from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[2]


def test_python_310_installs_tomllib_backport() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert 'tomli>=2.0.0; python_version < "3.11"' in pyproject["project"]["dependencies"]


def test_config_uses_tomli_fallback() -> None:
    source = (ROOT / "src" / "McuBuddy" / "config.py").read_text(encoding="utf-8")

    assert "except ModuleNotFoundError:" in source
    assert "import tomli as tomllib" in source
