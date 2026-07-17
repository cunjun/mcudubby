from importlib.metadata import version

import mcudubby


def test_package_version_matches_installed_distribution_metadata() -> None:
    assert mcudubby.__version__ == version("mcudubby")
