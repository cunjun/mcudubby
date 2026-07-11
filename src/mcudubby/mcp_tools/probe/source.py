from __future__ import annotations

from ...session import SessionState
from ...tools import probe as probe_tools


def register_probe_source_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def elf_addr_to_source(address: int) -> dict:
        """Look up the source file and line number for a given address using DWARF .debug_line.

        Returns file name, line number, and nearest function symbol.
        Requires ELF loaded with DWARF debug info.
        Example: elf_addr_to_source(0x08001234)
        """
        return probe_tools.addr_to_source(session, address=address)

    @mcp.tool()
    async def source_step() -> dict:
        """Execute instructions until the source line changes (source-level single step).

        Uses DWARF .debug_line to detect line boundaries. Falls back to a single
        instruction step if no DWARF info is available.
        Requires ELF loaded with DWARF info and probe connected and target halted.
        """
        return probe_tools.source_step(session)

    @mcp.tool()
    async def disassemble(address: int, count: int = 10) -> dict:
        """Disassemble Thumb/Thumb-2 instructions at the given address.

        Reads count*4 bytes from target memory and disassembles using capstone.
        Annotates each instruction with source file:line if DWARF is loaded.
        Requires probe connected and target halted.
        Example: disassemble(0x08001234, 10)
        """
        return probe_tools.disassemble(session, address=address, count=count)

    @mcp.tool()
    async def get_locals() -> dict:
        """Read local variables and parameters at the current PC using DWARF .debug_info.

        Resolves each variable's location (stack offset, register, or absolute address)
        and reads its current value from the target. Variables optimized out or using
        complex location expressions will have value=null.
        Requires ELF with DWARF loaded and probe connected and target halted.
        """
        return probe_tools.get_locals(session)

    @mcp.tool()
    async def set_local(name: str, value: int, confirm: bool = False) -> dict:
        """Write an integer value to a local variable by name at the current PC.

        Resolves the variable's location via DWARF .debug_info and writes the value
        to the corresponding stack address or absolute address.
        Variables in registers or with complex locations cannot be written this way.
        Requires ELF with DWARF loaded and probe connected and target halted.
        Example: set_local('count', 0)
        """
        return probe_tools.set_local(session, name=name, value=value, confirm=confirm)

    @mcp.tool()
    async def run_to_source(file: str, line: int, timeout_seconds: float = 10.0) -> dict:
        """Run target until execution reaches a specific source file and line number.

        Looks up the address for file:line in the DWARF line table, sets a
        breakpoint there, and resumes. Matches on filename suffix so you can
        pass just the basename (e.g. 'main.c') or a full path.
        Requires ELF with DWARF loaded and probe connected.
        Example: run_to_source('main.c', 42)
        """
        return probe_tools.run_to_source(
            session, file=file, line=line, timeout_seconds=timeout_seconds
        )

    @mcp.tool()
    async def run_to_function(name: str, timeout_seconds: float = 10.0) -> dict:
        """Set a breakpoint on a function by name, resume, and wait for it to be hit.

        Combines set_breakpoint + continue_target into one step.
        Requires ELF loaded and probe connected.
        Example: run_to_function('HAL_UART_Transmit')
        Example: run_to_function('main', timeout_seconds=3.0)
        """
        return probe_tools.run_to_function(session, name=name, timeout_seconds=timeout_seconds)

    @mcp.tool()
    async def dwarf_backtrace(max_frames: int = 16) -> dict:
        """Accurate call stack using DWARF .debug_frame CFI rules.

        For each frame, computes the Canonical Frame Address (CFA) from the CFI
        table and reads the saved return address from the stack. Falls back to LR
        for leaf functions or frames without CFI entries.
        More accurate than the heuristic backtrace(); requires ELF with .debug_frame.
        Requires probe connected and target halted.
        """
        return probe_tools.dwarf_backtrace(session, max_frames=max_frames)

    @mcp.tool()
    async def backtrace(max_frames: int = 20, stack_scan_words: int = 64) -> dict:
        """Heuristic call stack reconstruction for Cortex-M targets.

        Frame 0 is the current PC. Frame 1 is LR (return address).
        Further frames are found by scanning the stack for addresses that
        resolve to known function symbols in the loaded ELF.
        Accuracy depends on compiler optimizations; best with -O0 or -O1.
        Requires probe connected and target halted.
        """
        return probe_tools.backtrace(
            session, max_frames=max_frames, stack_scan_words=stack_scan_words
        )

    @mcp.tool()
    async def step_out(timeout_seconds: float = 5.0) -> dict:
        """Run until the current function returns (step out).

        Sets a breakpoint at the current LR (return address) and resumes.
        Requires probe connected and target halted.
        """
        return probe_tools.step_out(session, timeout_seconds=timeout_seconds)

    @mcp.tool()
    async def step_over() -> dict:
        """Execute one source line, stepping OVER function calls (bl/blx).

        Disassembles the current instruction. If it is a BL/BLX call, sets a
        breakpoint at the return address and resumes, skipping the callee body.
        Otherwise falls through to source_step (step into).
        Requires probe connected and target halted.
        """
        return probe_tools.step_over(session)
