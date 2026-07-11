from __future__ import annotations

from ...session import SessionState
from ...tools import probe as probe_tools


def register_probe_control_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def list_connected_probes() -> dict:
        """List all probes currently connected to this machine. Start here if unsure what probe to use."""
        return probe_tools.list_connected_probes(session)

    @mcp.tool()
    async def probe_connect(target: str, unique_id: str | None = None) -> dict:
        return probe_tools.connect_probe(session, target=target, unique_id=unique_id)

    @mcp.tool()
    async def probe_disconnect() -> dict:
        return probe_tools.disconnect_probe(session)

    @mcp.tool()
    async def probe_halt() -> dict:
        return probe_tools.halt_target(session)

    @mcp.tool()
    async def probe_resume() -> dict:
        return probe_tools.resume_target(session)

    @mcp.tool()
    async def probe_reset(halt: bool = False) -> dict:
        return probe_tools.reset_target(session, halt=halt)

    @mcp.tool()
    async def set_breakpoint(
        symbol: str | None = None,
        address: int | None = None,
        condition_symbol: str | None = None,
        condition_register: str | None = None,
        condition_op: str = "eq",
        condition_value: int = 0,
        confirm: bool = False,
    ) -> dict:
        """Set a breakpoint, optionally with a condition.

        If condition_symbol or condition_register is given, continue_target will
        automatically skip this breakpoint (resume) whenever the condition is not met.
        condition_op: eq | ne | lt | gt | le | ge
        """
        return probe_tools.set_breakpoint(
            session,
            symbol=symbol,
            address=address,
            condition_symbol=condition_symbol,
            condition_register=condition_register,
            condition_op=condition_op,
            condition_value=condition_value,
            confirm=confirm,
        )

    @mcp.tool()
    async def list_conditional_breakpoints() -> dict:
        """List all registered conditional breakpoints in the current session."""
        return probe_tools.list_conditional_breakpoints(session)

    @mcp.tool()
    async def set_breakpoints_for_function_range(start_symbol: str, end_symbol: str) -> dict:
        """Set breakpoints on all ELF functions whose address falls between two symbols.

        Useful for tracing all calls within a module (e.g. start=_uart_start, end=_uart_end).
        Requires ELF loaded and probe connected.
        """
        return probe_tools.set_breakpoints_for_function_range(
            session, start_symbol=start_symbol, end_symbol=end_symbol
        )

    @mcp.tool()
    async def clear_breakpoint(
        symbol: str | None = None,
        address: int | None = None,
        confirm: bool = False,
    ) -> dict:
        return probe_tools.clear_breakpoint(
            session, symbol=symbol, address=address, confirm=confirm
        )

    @mcp.tool()
    async def clear_all_breakpoints(confirm: bool = False) -> dict:
        return probe_tools.clear_all_breakpoints(session, confirm=confirm)

    @mcp.tool()
    async def continue_target(
        timeout_seconds: float = 5.0,
        poll_interval_ms: int = 50,
        max_condition_loops: int = 1000,
    ) -> dict:
        """Resume target execution.

        max_condition_loops: max number of conditional breakpoint skips before giving up.
        Lower this (e.g. 10) for high-frequency breakpoints where you want an early abort.
        """
        return probe_tools.continue_target(
            session,
            timeout_seconds=timeout_seconds,
            poll_interval_ms=poll_interval_ms,
            max_condition_loops=max_condition_loops,
        )

    @mcp.tool()
    async def read_stopped_context(
        include_fault_registers: bool = True,
        include_logs: bool = False,
        log_tail_lines: int = 20,
        resolve_symbols: bool = True,
    ) -> dict:
        return probe_tools.read_stopped_context(
            session,
            include_fault_registers=include_fault_registers,
            include_logs=include_logs,
            log_tail_lines=log_tail_lines,
            resolve_symbols=resolve_symbols,
        )

    @mcp.tool()
    async def probe_step() -> dict:
        """Execute one instruction and return the new PC (with symbol if ELF is loaded)."""
        return probe_tools.step_instruction(session)
