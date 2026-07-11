from __future__ import annotations

from ..session import SessionState
from ..tools.diagnose import diagnose_hardfault as _diagnose_hardfault
from ..tools.diagnose import diagnose_startup_failure as _diagnose_startup_failure
from ..tools.diagnose_router import diagnose as _diagnose
from ..tools.phase3 import diagnose_clock_issue as _diagnose_clock_issue
from ..tools.phase3 import diagnose_interrupt_issue as _diagnose_interrupt_issue
from ..tools.phase3 import diagnose_peripheral_stuck as _diagnose_peripheral_stuck
from ..tools.phase3 import diagnose_stack_overflow as _diagnose_stack_overflow


def register_diagnostic_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def diagnose_peripheral_stuck(peripheral: str, symptom: str | None = None) -> dict:
        """Diagnose why a peripheral is not working.

        Reads peripheral registers (via SVD) and checks RCC clock enable.
        Common root causes: clock not enabled in RCC, wrong pin AF mode, wrong baud rate.
        Requires SVD loaded and probe connected.
        Example: diagnose_peripheral_stuck('USART2', 'no output from TX pin')
        """
        return _diagnose_peripheral_stuck(session, peripheral=peripheral, symptom=symptom)

    @mcp.tool()
    async def diagnose_stack_overflow() -> dict:
        """Diagnose potential stack overflow on a Cortex-M target.

        Reads VTOR (0xE000ED08) to locate the vector table, extracts the
        initial SP from word 0, and compares it with the current SP.
        If an ELF is loaded and _Min_Stack_Size is available, reports
        remaining stack space and detects overflow.
        Requires probe connected and target halted.
        """
        return _diagnose_stack_overflow(session)

    @mcp.tool()
    async def diagnose_interrupt_issue() -> dict:
        return _diagnose_interrupt_issue(session)

    @mcp.tool()
    async def diagnose_clock_issue() -> dict:
        return _diagnose_clock_issue(session)

    @mcp.tool()
    async def diagnose_hardfault(
        auto_halt: bool = True,
        include_logs: bool = True,
        log_tail_lines: int = 50,
        resolve_symbols: bool = True,
        include_fault_registers: bool = True,
        include_stack_snapshot: bool = True,
        stack_snapshot_bytes: int = 64,
        suspected_stage: str | None = None,
    ) -> dict:
        return _diagnose_hardfault(
            session,
            auto_halt=auto_halt,
            include_logs=include_logs,
            log_tail_lines=log_tail_lines,
            resolve_symbols=resolve_symbols,
            include_fault_registers=include_fault_registers,
            include_stack_snapshot=include_stack_snapshot,
            stack_snapshot_bytes=stack_snapshot_bytes,
            suspected_stage=suspected_stage,
        )

    @mcp.tool()
    async def diagnose_startup_failure(
        auto_halt: bool = True,
        include_logs: bool = True,
        log_tail_lines: int = 50,
        resolve_symbols: bool = True,
        suspected_stage: str | None = None,
    ) -> dict:
        return _diagnose_startup_failure(
            session,
            auto_halt=auto_halt,
            include_logs=include_logs,
            log_tail_lines=log_tail_lines,
            resolve_symbols=resolve_symbols,
            suspected_stage=suspected_stage,
        )

    @mcp.tool()
    async def diagnose(
        symptom: str,
        peripheral: str | None = None,
        suspected_stage: str | None = None,
        include_logs: bool = True,
        auto_halt: bool = True,
        stack_canary: int = 0xCCCCCCCC,
    ) -> dict:
        """Route a user-level symptom to the most relevant diagnosis tool.

        Examples:
        - diagnose("Board crashed into HardFault")
        - diagnose("USART2 no output from TX pin", peripheral="USART2")
        - diagnose("PLL clock switch is stuck")
        """
        return _diagnose(
            session,
            symptom=symptom,
            peripheral=peripheral,
            suspected_stage=suspected_stage,
            include_logs=include_logs,
            auto_halt=auto_halt,
            stack_canary=stack_canary,
        )
