from __future__ import annotations

from ..session import SessionState
from ..tools.lifecycle import disconnect_all as _disconnect_all
from ..tools.logs import connect_log as _connect_log
from ..tools.logs import disconnect_log as _disconnect_log
from ..tools.logs import tail_logs as _tail_logs


def register_io_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def elf_load(path: str) -> dict:
        return session.elf.load(path)

    @mcp.tool()
    async def log_connect(port: str, baudrate: int = 115200) -> dict:
        return _connect_log(session, port=port, baudrate=baudrate)

    @mcp.tool()
    async def log_disconnect() -> dict:
        return _disconnect_log(session)

    @mcp.tool()
    async def log_tail(line_count: int = 50) -> dict:
        return _tail_logs(session, line_count=line_count)

    @mcp.tool()
    async def disconnect_all() -> dict:
        return _disconnect_all(session)
