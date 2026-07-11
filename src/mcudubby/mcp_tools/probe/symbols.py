from __future__ import annotations

from ...session import SessionState
from ...tools import probe as probe_tools


def register_probe_symbol_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def watch_symbol(
        name: str,
        size: int = 4,
        timeout_seconds: float = 10.0,
        poll_interval_seconds: float = 0.1,
    ) -> dict:
        """Poll a symbol's value until it changes or timeout expires.

        Reads the symbol at each poll interval and returns as soon as the value differs
        from the initial read. Reports old/new values and elapsed time.
        Requires ELF loaded and probe connected.
        Example: watch_symbol('g_state', 4, timeout_seconds=5.0)
        """
        return probe_tools.watch_symbol(
            session,
            name=name,
            size=size,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    @mcp.tool()
    async def elf_list_functions(name_filter: str | None = None) -> dict:
        """List all function symbols from the loaded ELF with address and size.

        name_filter: optional substring to filter function names (case-insensitive).
        Useful for finding candidate breakpoint locations without a map file.
        Example: elf_list_functions('uart')  → all UART-related functions
        Requires ELF loaded (no probe needed).
        """
        return probe_tools.elf_list_functions(session, name_filter=name_filter)

    @mcp.tool()
    async def elf_symbol_info(name: str) -> dict:
        """Return address, size, type, and source location for a single symbol.

        Looks up the exact symbol name in the ELF symbol table.
        Useful for checking a variable's address before setting a watchpoint.
        Example: elf_symbol_info('g_uart_handle')
        Example: elf_symbol_info('SystemCoreClock')
        Requires ELF loaded (no probe needed).
        """
        return probe_tools.elf_symbol_info(session, name=name)

    @mcp.tool()
    async def read_symbol_value(name: str, size: int = 4) -> dict:
        """Read the value of a symbol (variable, linker symbol) by name from target memory.

        Resolves the symbol address via ELF, then reads 'size' bytes at that address.
        Returns raw bytes plus u8/u16/u32 interpretations (little-endian).
        Requires ELF loaded and probe connected.
        Example: read_symbol_value('g_error_count', 4)
        Example: read_symbol_value('_Min_Stack_Size', 4)
        """
        return probe_tools.read_symbol_value(session, name=name, size=size)

    @mcp.tool()
    async def write_symbol_value(
        name: str,
        value: int,
        size: int = 4,
        confirm: bool = False,
    ) -> dict:
        """Write an integer value to a symbol (variable) by name in target memory.

        Resolves the symbol address via ELF, then writes 'size' bytes (little-endian).
        Requires ELF loaded and probe connected.
        Example: write_symbol_value('g_error_count', 0, 4)
        Example: write_symbol_value('g_mode', 1, 1)
        """
        return probe_tools.write_symbol_value(
            session, name=name, value=value, size=size, confirm=confirm
        )
