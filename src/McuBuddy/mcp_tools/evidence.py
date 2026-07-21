from __future__ import annotations

from ..session import SessionState
from ..tools.evidence import collect_crash_evidence as _collect_crash_evidence
from ..tools.evidence import collect_peripheral_evidence as _collect_peripheral_evidence
from ..tools.evidence import collect_rtos_evidence as _collect_rtos_evidence
from ..tools.evidence import collect_startup_evidence as _collect_startup_evidence


def register_evidence_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def collect_crash_evidence(
        auto_halt: bool = True,
        include_logs: bool = True,
        log_tail_lines: int = 50,
        resolve_symbols: bool = True,
        include_stack_snapshot: bool = True,
        stack_snapshot_bytes: int = 64,
    ) -> dict:
        """Collect structured crash facts without assigning a root cause."""
        return _collect_crash_evidence(
            session,
            auto_halt=auto_halt,
            include_logs=include_logs,
            log_tail_lines=log_tail_lines,
            resolve_symbols=resolve_symbols,
            include_stack_snapshot=include_stack_snapshot,
            stack_snapshot_bytes=stack_snapshot_bytes,
        )

    @mcp.tool()
    async def collect_startup_evidence(
        reset_and_halt: bool = False,
        include_logs: bool = True,
        log_tail_lines: int = 50,
        resolve_symbols: bool = True,
    ) -> dict:
        """Collect reset, vector, context, and log facts for startup failures."""
        return _collect_startup_evidence(
            session,
            reset_and_halt=reset_and_halt,
            include_logs=include_logs,
            log_tail_lines=log_tail_lines,
            resolve_symbols=resolve_symbols,
        )

    @mcp.tool()
    async def collect_peripheral_evidence(
        peripheral: str,
        include_rcc: bool = True,
        include_gpio: bool = True,
    ) -> dict:
        """Collect SVD-backed peripheral, RCC, and GPIO facts."""
        return _collect_peripheral_evidence(
            session,
            peripheral=peripheral,
            include_rcc=include_rcc,
            include_gpio=include_gpio,
        )

    @mcp.tool()
    async def collect_rtos_evidence(
        task_name: str | None = None,
        max_priorities: int = 32,
        task_name_len: int = 16,
    ) -> dict:
        """Collect FreeRTOS task and optional task-context facts."""
        return _collect_rtos_evidence(
            session,
            task_name=task_name,
            max_priorities=max_priorities,
            task_name_len=task_name_len,
        )
