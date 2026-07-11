from __future__ import annotations

from ...session import SessionState
from ...tools import probe as probe_tools


def register_probe_watch_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def probe_set_watchpoint(
        address: int,
        size: int = 4,
        watch_type: str = "write",
        confirm: bool = False,
    ) -> dict:
        """Set a hardware data watchpoint on a memory address.

        Halts the target when the address is accessed according to watch_type.
        watch_type: 'read', 'write', or 'read_write'
        size: number of bytes to watch (1, 2, or 4; Cortex-M supports up to 4 watchpoints)
        Requires probe connected and target halted.
        Example: probe_set_watchpoint(0x20000010, 4, 'write')
        """
        return probe_tools.set_watchpoint(
            session, address=address, size=size, watch_type=watch_type, confirm=confirm
        )

    @mcp.tool()
    async def probe_remove_watchpoint(address: int, confirm: bool = False) -> dict:
        """Remove a hardware watchpoint at the given address."""
        return probe_tools.remove_watchpoint(session, address=address, confirm=confirm)

    @mcp.tool()
    async def probe_clear_all_watchpoints(confirm: bool = False) -> dict:
        """Remove all hardware watchpoints."""
        return probe_tools.clear_all_watchpoints(session, confirm=confirm)

    @mcp.tool()
    async def probe_read_registers() -> dict:
        return probe_tools.read_registers(session)

    @mcp.tool()
    async def probe_read_fpu_registers() -> dict:
        return probe_tools.read_fpu_registers(session)

    @mcp.tool()
    async def read_cycle_counter() -> dict:
        """Read the DWT cycle counter when supported by the active probe backend.

        Useful for lightweight execution progress and timing checks.
        Requires probe connected.
        """
        return probe_tools.read_cycle_counter(session)

    @mcp.tool()
    async def read_swo_log(
        cpu_speed_hz: int,
        swo_speed_hz: int,
        max_bytes: int = 1024,
        port_mask: int = 0x01,
    ) -> dict:
        """Read bytes from the J-Link SWO host buffer when supported by the active probe backend.

        cpu_speed_hz: target CPU clock in Hz
        swo_speed_hz: SWO bitrate in Hz
        max_bytes: maximum bytes to return
        port_mask: ITM stimulus port mask used when enabling SWO
        Requires probe connected.
        """
        return probe_tools.read_swo_log(
            session,
            cpu_speed_hz=cpu_speed_hz,
            swo_speed_hz=swo_speed_hz,
            max_bytes=max_bytes,
            port_mask=port_mask,
        )

    @mcp.tool()
    async def probe_read_mpu_regions(confirm: bool = False) -> dict:
        return probe_tools.read_mpu_regions(session, confirm=confirm)

    @mcp.tool()
    async def probe_continue_until(
        address: int,
        condition_symbol: str | None = None,
        condition_register: str | None = None,
        condition_op: str = "eq",
        condition_value: int = 0,
        max_hits: int = 20,
        timeout_seconds: float = 5.0,
    ) -> dict:
        return probe_tools.continue_until(
            session,
            address=address,
            condition_symbol=condition_symbol,
            condition_register=condition_register,
            condition_op=condition_op,
            condition_value=condition_value,
            max_hits=max_hits,
            timeout_seconds=timeout_seconds,
        )
