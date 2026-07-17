from __future__ import annotations

from ..session import SessionState
from ..tools.build import build_project as _build_project
from ..tools.build import flash_firmware as _flash_firmware
from ..tools.gdb_server import get_gdb_server_status as _get_gdb_server_status
from ..tools.gdb_server import get_jlink_gdb_server_status as _get_jlink_gdb_server_status
from ..tools.gdb_server import start_gdb_server as _start_gdb_server
from ..tools.gdb_server import start_jlink_gdb_server as _start_jlink_gdb_server
from ..tools.gdb_server import stop_gdb_server as _stop_gdb_server
from ..tools.gdb_server import stop_jlink_gdb_server as _stop_jlink_gdb_server


def register_build_debug_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def build_project(timeout_seconds: int = 120) -> dict:
        return _build_project(session, timeout_seconds=timeout_seconds)

    @mcp.tool()
    async def flash_firmware(timeout_seconds: int = 120, confirm: bool = False) -> dict:
        return _flash_firmware(session, timeout_seconds=timeout_seconds, confirm=confirm)

    @mcp.tool()
    async def start_gdb_server(
        port: int = 3333,
        telnet_port: int = 4444,
        probe_server_port: int = 5555,
        allow_remote: bool = False,
        confirm_remote: bool = False,
        persist: bool = False,
        target: str | None = None,
        unique_id: str | None = None,
        elf_path: str | None = None,
    ) -> dict:
        """Start a pyOCD GDB server for the configured target.

        Uses the current probe config when target/unique_id are omitted.
        Example: start_gdb_server()
        Example: start_gdb_server(port=3334, persist=True)
        """
        return _start_gdb_server(
            session,
            port=port,
            telnet_port=telnet_port,
            probe_server_port=probe_server_port,
            allow_remote=allow_remote,
            confirm_remote=confirm_remote,
            persist=persist,
            target=target,
            unique_id=unique_id,
            elf_path=elf_path,
        )

    @mcp.tool()
    async def stop_gdb_server(timeout_seconds: float = 5.0) -> dict:
        """Stop the active pyOCD GDB server process if one is running."""
        return _stop_gdb_server(session, timeout_seconds=timeout_seconds)

    @mcp.tool()
    async def get_gdb_server_status() -> dict:
        """Return whether the pyOCD GDB server is running and which ports it uses."""
        return _get_gdb_server_status(session)

    @mcp.tool()
    async def start_jlink_gdb_server(
        target: str | None = None,
        serial_no: str | None = None,
        port: int = 2331,
        interface: str = "swd",
        speed: int = 4000,
        exe_path: str | None = None,
    ) -> dict:
        """Start a J-Link GDB server for the configured target.

        Uses the current probe config when target/serial_no are omitted.
        Example: start_jlink_gdb_server(target='STM32F103C8', serial_no='240710115')
        Example: start_jlink_gdb_server(port=2332, speed=1000)
        """
        return _start_jlink_gdb_server(
            session,
            target=target,
            serial_no=serial_no,
            port=port,
            interface=interface,
            speed=speed,
            exe_path=exe_path,
        )

    @mcp.tool()
    async def stop_jlink_gdb_server(timeout_seconds: float = 5.0) -> dict:
        """Stop the active J-Link GDB server process if one is running."""
        return _stop_jlink_gdb_server(session, timeout_seconds=timeout_seconds)

    @mcp.tool()
    async def get_jlink_gdb_server_status() -> dict:
        """Return whether the J-Link GDB server is running and which port it uses."""
        return _get_jlink_gdb_server_status(session)
