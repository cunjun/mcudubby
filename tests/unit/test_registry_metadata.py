import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
REGISTRY_NAME = "io.github.cunjun/mcubuddy"


def test_registry_metadata_matches_pypi_distribution() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    metadata = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))

    assert f"mcp-name: {REGISTRY_NAME}" in readme
    assert metadata["name"] == REGISTRY_NAME
    assert metadata["version"] == "0.6.0"
    assert metadata["repository"] == {
        "url": "https://github.com/cunjun/McuBuddy",
        "source": "github",
    }
    assert metadata["packages"] == [
        {
            "registryType": "pypi",
            "identifier": "McuBuddy",
            "version": "0.6.0",
            "transport": {"type": "stdio"},
        }
    ]
