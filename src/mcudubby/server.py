from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .mcp_tools import register_all_tools
from .session import SessionState


def create_server(session: SessionState | None = None) -> FastMCP:
    app = FastMCP("mcudubby")
    register_all_tools(app, session or SessionState())
    return app


mcp = create_server()


def main() -> None:
    mcp.run()
