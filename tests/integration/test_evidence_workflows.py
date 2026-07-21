from __future__ import annotations

import asyncio

from McuBuddy.server import create_server
from McuBuddy.session import SessionState


def test_evidence_tools_are_available_in_default_core_profile() -> None:
    app = create_server(SessionState())

    names = set(app._tool_manager._tools)

    assert "collect_crash_evidence" in names
    assert "collect_startup_evidence" in names
    assert "collect_peripheral_evidence" in names
    assert "collect_rtos_evidence" in names
    assert "diagnose" not in names


def test_full_profile_keeps_diagnostics_and_evidence_tools() -> None:
    app = create_server(SessionState(), tool_profile="full")

    names = set(app._tool_manager._tools)

    assert "diagnose" in names
    assert "run_debug_loop" in names
    assert "collect_crash_evidence" in names


def test_mcp_crash_evidence_returns_standard_envelope_when_probe_missing() -> None:
    async def scenario() -> dict:
        app = create_server(SessionState())
        tool = app._tool_manager.get_tool("collect_crash_evidence")
        return await tool.run({})

    result = asyncio.run(scenario())

    assert result["status"] == "error"
    assert "evidence" in result
    assert result["safety"]["level"] == "execution-changing"
