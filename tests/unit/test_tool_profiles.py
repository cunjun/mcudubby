from __future__ import annotations

import pytest

from McuBuddy.tool_profiles import (
    CORE_TOOL_NAMES,
    PROFILE_ENV_VAR,
    ToolProfileError,
    resolve_tool_profile,
)


def test_default_profile_is_core() -> None:
    profile = resolve_tool_profile(environ={})

    assert profile.name == "core"
    assert profile.enabled_tool_names == CORE_TOOL_NAMES
    assert profile.allows("doctor") is True
    assert profile.allows("diagnose") is False
    assert profile.allows("probe_write_memory") is False


def test_environment_can_select_full_profile() -> None:
    profile = resolve_tool_profile(environ={PROFILE_ENV_VAR: "full"})

    assert profile.name == "full"
    assert profile.enabled_tool_names is None
    assert profile.allows("diagnose") is True


def test_explicit_profile_overrides_environment() -> None:
    profile = resolve_tool_profile("core", environ={PROFILE_ENV_VAR: "full"})

    assert profile.name == "core"


def test_profile_values_are_case_and_whitespace_tolerant() -> None:
    assert resolve_tool_profile(" FULL ").name == "full"


def test_unknown_profile_lists_valid_values() -> None:
    with pytest.raises(ToolProfileError, match="core, full"):
        resolve_tool_profile("expert", environ={})


def test_core_tool_names_are_unique_and_immutable() -> None:
    assert isinstance(CORE_TOOL_NAMES, frozenset)
    assert len(CORE_TOOL_NAMES) == len(set(CORE_TOOL_NAMES))
