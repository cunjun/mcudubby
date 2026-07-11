from __future__ import annotations

from ..session import SessionState
from .build_debug import register_build_debug_tools
from .diagnostics import register_diagnostic_tools
from .io import register_io_tools
from .probe import register_probe_tools
from .runtime import register_runtime_tools
from .svd import register_svd_tools


def register_all_tools(mcp, session: SessionState) -> None:
    register_runtime_tools(mcp, session)
    register_build_debug_tools(mcp, session)
    register_probe_tools(mcp, session)
    register_io_tools(mcp, session)
    register_svd_tools(mcp, session)
    register_diagnostic_tools(mcp, session)
