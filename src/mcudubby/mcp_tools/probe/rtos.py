from __future__ import annotations

from ...session import SessionState
from ...tools import probe as probe_tools


def register_probe_rtos_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def read_stack_usage(
        canary: int = 0xA5A5A5A5,
        task_name_len: int = 16,
        max_priorities: int = 32,
    ) -> dict:
        """Scan FreeRTOS task stacks for the canary high-water mark.

        FreeRTOS fills unused stack with 0xa5 (tskSTACK_FILL_BYTE).
        Scans each task's stack from base upward and counts intact canary words.
        Reports min_free_bytes (never-used stack) per task.
        canary: fill byte pattern used at init (default 0xa5a5a5a5).
        max_priorities: upper bound for scanning pxReadyTasksLists (default 32).
        Requires ELF loaded and probe connected with target halted.
        """
        return probe_tools.read_stack_usage(
            session,
            canary=canary,
            task_name_len=task_name_len,
            max_priorities=max_priorities,
        )

    @mcp.tool()
    async def diagnose_memory_corruption(stack_canary: int = 0xCCCCCCCC) -> dict:
        """Scan stack and heap regions for corruption evidence.

        Reads stack bounds from ELF linker symbols (_estack / _Min_Stack_Size or __StackTop / __StackLimit),
        checks whether current SP is in bounds, scans for stack canary high-water mark,
        and samples heap boundaries for known corruption magic values.

        stack_canary: 4-byte fill pattern written to unused stack at startup (default 0xCCCCCCCC).
        Common values: 0xCCCCCCCC (Keil/IAR default), 0xDEADBEEF, 0xA5A5A5A5.
        Requires ELF loaded and probe connected.
        """
        return probe_tools.diagnose_memory_corruption(session, stack_canary=stack_canary)

    @mcp.tool()
    async def list_rtos_tasks(max_priorities: int = 32, task_name_len: int = 16) -> dict:
        """List all FreeRTOS tasks with state, priority, and stack usage.

        Walks pxReadyTasksLists, xDelayedTaskList*, and xSuspendedTaskList to enumerate
        all tasks. Reads TCB fields: name, priority, stack base, stack top pointer.

        max_priorities: upper bound for scanning pxReadyTasksLists (default 32).
        task_name_len: configMAX_TASK_NAME_LEN in your FreeRTOS build (default 16).
        Requires ELF loaded and probe connected with target halted.
        """
        return probe_tools.list_rtos_tasks(
            session, max_priorities=max_priorities, task_name_len=task_name_len
        )

    @mcp.tool()
    async def rtos_task_context(task_name: str, task_name_len: int = 16) -> dict:
        """Read the saved register context of a blocked or suspended FreeRTOS task.

        Parses the Cortex-M4F context switch stack frame stored in the task's TCB.
        Reconstructs R0-R12, SP, LR, PC, xPSR and resolves PC to a symbol/source line.
        Automatically detects whether FPU context was saved (EXC_RETURN bit 4).
        If the named task is currently running, returns live register values instead.

        task_name: exact task name as passed to xTaskCreate (case-sensitive).
        task_name_len: configMAX_TASK_NAME_LEN in your FreeRTOS build (default 16).
        Requires ELF loaded and probe connected with target halted.
        """
        return probe_tools.rtos_task_context(
            session, task_name=task_name, task_name_len=task_name_len
        )

    @mcp.tool()
    async def rtos_switch_context(task_name: str, task_name_len: int = 16) -> dict:
        """Switch CPU context to a blocked or suspended FreeRTOS task.

        Uses the saved exception frame from the task's stack (stored in TCB.pxTopOfStack),
        constructs a new exception frame on the current stack, and sets LR to EXC_RETURN
        so that stepping once enters the task context. After switching, you can step
        or continue to execute the target task.
        Requires ELF loaded and probe connected with target halted.
        Example: rtos_switch_context('idle_task')
        """
        return probe_tools.rtos_switch_context(
            session, task_name=task_name, task_name_len=task_name_len
        )

    @mcp.tool()
    async def read_rtt_log(
        channel: int = 0,
        max_bytes: int = 4096,
        search_start: int = 0x20000000,
        search_size: int = 0x50000,
    ) -> dict:
        """Read Segger RTT log output directly from target RAM via probe (no UART needed).

        Scans the specified RAM range for the RTT control block ('SEGGER RTT' magic),
        then reads the ring buffer of the requested up-channel.

        channel: RTT up-channel index (default 0).
        search_start: start of RAM scan (default 0x20000000).
        search_size: bytes to scan (default 0x50000 = 320 KB).
        Requires probe connected and target halted (or briefly halted to read).
        """
        return probe_tools.read_rtt_log(
            session,
            channel=channel,
            max_bytes=max_bytes,
            search_start=search_start,
            search_size=search_size,
        )
