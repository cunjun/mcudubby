from __future__ import annotations

from ...session import SessionState
from .control import register_probe_control_tools
from .memory import register_probe_memory_tools
from .rtos import register_probe_rtos_tools
from .source import register_probe_source_tools
from .symbols import register_probe_symbol_tools
from .trace import register_probe_trace_tools
from .watch import register_probe_watch_tools


def register_probe_tools(mcp, session: SessionState) -> None:
    register_probe_control_tools(mcp, session)
    register_probe_source_tools(mcp, session)
    register_probe_memory_tools(mcp, session)
    register_probe_trace_tools(mcp, session)
    register_probe_rtos_tools(mcp, session)
    register_probe_symbol_tools(mcp, session)
    register_probe_watch_tools(mcp, session)
