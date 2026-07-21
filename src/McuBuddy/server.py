from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .mcp_tools import register_all_tools
from .session import SessionState
from .tool_profiles import ToolProfile, resolve_tool_profile


def create_server(
    session: SessionState | None = None,
    *,
    tool_profile: str | ToolProfile | None = None,
) -> FastMCP:
    profile = (
        tool_profile
        if isinstance(tool_profile, ToolProfile)
        else resolve_tool_profile(tool_profile)
    )
    app = FastMCP("McuBuddy")
    register_all_tools(app, session or SessionState(), tool_profile=profile)
    return app


mcp = create_server()


def main() -> None:
    from .cli import main as cli_main

    raise SystemExit(cli_main())
