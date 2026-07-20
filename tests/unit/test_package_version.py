from importlib.metadata import version

import McuBubby


def test_package_version_matches_installed_distribution_metadata() -> None:
    assert McuBubby.__version__ == version("McuBubby")
