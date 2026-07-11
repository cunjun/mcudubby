from __future__ import annotations

from ...session import SessionState
from ...tools import probe as probe_tools


def register_probe_trace_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def log_trace(max_steps: int = 200, max_lines: int = 50) -> dict:
        """Step through code and record each unique source line visited.

        Executes up to max_steps instructions, collecting distinct (file, line) pairs
        in execution order. Stops early when max_lines unique lines are reached.
        Useful for tracing execution paths through unfamiliar code.
        Requires ELF with debug info (.debug_line) and probe connected.
        """
        return probe_tools.log_trace(session, max_steps=max_steps, max_lines=max_lines)

    @mcp.tool()
    async def reset_and_trace(max_steps: int = 200, max_lines: int = 50) -> dict:
        """Reset the target and immediately trace execution from the reset vector.

        Calls reset(halt=True) then steps through code collecting unique source lines.
        Useful for seeing the startup path (clocks, peripherals, RTOS init).
        Requires ELF with debug info and probe connected.
        """
        return probe_tools.reset_and_trace(session, max_steps=max_steps, max_lines=max_lines)
