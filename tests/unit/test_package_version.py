from importlib import import_module, util
from importlib.metadata import version


def test_package_version_matches_installed_distribution_metadata() -> None:
    assert util.find_spec("McuBuddy") is not None

    package = import_module("McuBuddy")
    assert package.__version__ == version("McuBuddy")
