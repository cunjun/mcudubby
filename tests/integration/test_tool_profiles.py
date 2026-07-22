from __future__ import annotations

import asyncio

from McuBuddy.server import create_server
from McuBuddy.session import SessionState
from McuBuddy.tool_profiles import CORE_TOOL_NAMES


def test_default_server_registers_exact_core_tool_set() -> None:
    app = create_server(SessionState())

    assert set(app._tool_manager._tools) == CORE_TOOL_NAMES
    assert "diagnose" not in app._tool_manager._tools
    assert "run_debug_loop" not in app._tool_manager._tools
    assert "probe_write_memory" not in app._tool_manager._tools


def test_full_server_registers_legacy_tools_plus_evidence() -> None:
    app = create_server(SessionState(), tool_profile="full")
    names = set(app._tool_manager._tools)

    assert len(names) == 114
    assert "diagnose" in names
    assert "run_debug_loop" in names
    assert "probe_write_memory" in names
    assert CORE_TOOL_NAMES.issubset(names)


def test_core_safety_query_defaults_to_visible_tools_only() -> None:
    async def scenario() -> tuple[set[str], dict]:
        app = create_server(SessionState())
        result = await app._tool_manager.get_tool("list_tool_safety").run({})
        return set(app._tool_manager._tools), result

    visible_names, result = asyncio.run(scenario())

    assert result["active_profile"] == "core"
    assert set(result["tools"]) == visible_names
    assert "probe_write_memory" not in result["tools"]


def test_core_safety_query_can_include_hidden_metadata_without_registering_tools() -> None:
    async def scenario() -> tuple[set[str], dict]:
        app = create_server(SessionState())
        result = await app._tool_manager.get_tool("list_tool_safety").run(
            {"include_hidden": True}
        )
        return set(app._tool_manager._tools), result

    visible_names, result = asyncio.run(scenario())

    assert "probe_write_memory" in result["tools"]
    assert set(create_server(SessionState())._tool_manager._tools) == visible_names
