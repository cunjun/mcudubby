from __future__ import annotations

from typing import Literal

from ...session import SessionState
from ...tools import probe as probe_tools


def register_probe_memory_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def erase_flash(
        start_address: int | None = None,
        end_address: int | None = None,
        chip_erase: bool = False,
        confirm: bool = False,
    ) -> dict:
        """Erase target flash memory.

        Use chip_erase=True to erase the whole chip, or provide start/end addresses for a range erase.
        Requires probe connected.
        """
        return probe_tools.erase_flash(
            session,
            start_address=start_address,
            end_address=end_address,
            chip_erase=chip_erase,
            confirm=confirm,
        )

    @mcp.tool()
    async def program_flash(
        address: int,
        data: list[int],
        verify: bool = True,
        confirm: bool = False,
    ) -> dict:
        """Program target flash memory from raw byte data.

        address: flash destination address
        data: list of byte values (0-255)
        verify: read back and compare after programming
        Requires probe connected.
        """
        return probe_tools.program_flash(
            session,
            address=address,
            data=data,
            verify=verify,
            confirm=confirm,
        )

    @mcp.tool()
    async def flash_image(
        path: str,
        address: int,
        erase_mode: Literal["sector", "chip"] = "sector",
        verify: bool = True,
        reset_after: bool = True,
        confirm: bool = False,
    ) -> dict:
        """Flash a raw binary file with erase, program, verify, and optional reset.

        path must be within security.allowed_file_paths when that allowlist is configured.
        erase_mode accepts 'sector' (default) or 'chip'. This persistent operation requires
        explicit confirmation and both flash erase and programming to be enabled.
        """
        return probe_tools.flash_image(
            session,
            path=path,
            address=address,
            erase_mode=erase_mode,
            verify=verify,
            reset_after=reset_after,
            confirm=confirm,
        )

    @mcp.tool()
    async def verify_flash(
        address: int,
        data: list[int],
    ) -> dict:
        """Verify target flash contents against expected raw byte data.

        address: flash start address
        data: expected byte values (0-255)
        Requires probe connected.
        """
        return probe_tools.verify_flash(session, address=address, data=data)

    @mcp.tool()
    async def probe_write_memory(address: int, data: list[int], confirm: bool = False) -> dict:
        """Write bytes to target memory. data is a list of integers (0-255)."""
        return probe_tools.write_memory(session, address=address, data=data, confirm=confirm)

    @mcp.tool()
    async def probe_read_memory(address: int, size: int) -> dict:
        """Read bytes from target memory at the given address.

        Returns raw bytes plus convenience integer interpretations (u8/u16/u32 little-endian).
        Requires probe connected and target halted.
        Example: probe_read_memory(0x20000000, 4)
        """
        return probe_tools.read_memory(session, address=address, size=size)

    @mcp.tool()
    async def dump_memory(
        address: int,
        size: int = 64,
        format: str = "hex",
        columns: int = 16,
    ) -> dict:
        """Read and display memory in formatted form.

        format options:
          'hex'  — classic hex dump with address, hex bytes, and ASCII sidebar
          'u8'   — array of unsigned bytes
          'u16'  — array of unsigned 16-bit values (little-endian)
          'u32'  — array of unsigned 32-bit values (little-endian)
          'u64'  — array of unsigned 64-bit values (little-endian)

        columns: bytes per row for hex format (default 16).
        Requires probe connected and target halted.
        Example: dump_memory(0x20000000, 64)
        Example: dump_memory(0x20000100, 32, 'u32')
        """
        return probe_tools.dump_memory(
            session, address=address, size=size, format=format, columns=columns
        )

    @mcp.tool()
    async def memory_find(
        address: int, size: int, pattern: list[int], max_results: int = 16
    ) -> dict:
        """Search a memory region for a byte pattern.

        Returns all non-overlapping match addresses. Useful for finding magic numbers,
        string literals, or corrupted canary values in RAM.
        pattern: list of byte values, e.g. [0xDE, 0xAD, 0xBE, 0xEF]
        Example: memory_find(0x20000000, 0x10000, [0xDE, 0xAD, 0xBE, 0xEF])
        Example: memory_find(0x20000000, 0x10000, [0x53, 0x45, 0x47, 0x47, 0x45, 0x52])
        """
        return probe_tools.memory_find(
            session, address=address, size=size, pattern=pattern, max_results=max_results
        )

    @mcp.tool()
    async def step_n_instructions(count: int = 10) -> dict:
        """Execute count assembly instructions, recording PC and symbol at each step.

        Returns a trace list. Useful for precisely tracking execution through
        small code sequences without source-level stepping.
        Maximum 100 steps per call (truncated=True if count exceeded).
        Requires probe connected and target halted.
        """
        return probe_tools.step_n_instructions(session, count=count)

    @mcp.tool()
    async def read_memory_map() -> dict:
        """Return the Cortex-M address space layout and ELF section map.

        Always returns the fixed Cortex-M region boundaries (Code/SRAM/Peripheral etc.).
        If an ELF is loaded, also returns each section's name, VMA, and size.
        No probe connection required.
        """
        return probe_tools.read_memory_map(session)

    @mcp.tool()
    async def compare_elf_to_flash() -> dict:
        """Compare all loadable ELF sections against actual target memory.

        Reads each PROGBITS+ALLOC section from the ELF, reads the same address range
        from target memory, and reports mismatching bytes. Useful for verifying that
        flash programming completed correctly.
        Requires ELF loaded and probe connected.
        """
        return probe_tools.compare_elf_to_flash(session)

    @mcp.tool()
    async def memory_snapshot(address: int, size: int, label: str = "default") -> dict:
        """Capture a memory region snapshot for later comparison.

        Use before an operation (step, continue, write) then call memory_diff to see what changed.
        Multiple snapshots can be stored simultaneously using different labels.
        Example: memory_snapshot(0x20000000, 256, 'before_init')
        """
        return probe_tools.memory_snapshot(session, address=address, size=size, label=label)

    @mcp.tool()
    async def memory_diff(label: str = "default") -> dict:
        """Re-read a snapshotted memory region and return a byte-level diff.

        Returns changed_bytes (individual byte changes) and changed_regions (grouped contiguous runs).
        Call memory_snapshot first to establish a baseline.
        Example: memory_diff('before_init')
        """
        return probe_tools.memory_diff(session, label=label)
