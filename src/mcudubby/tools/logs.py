from __future__ import annotations

from ..session import SessionState


def connect_log(session: SessionState, port: str, baudrate: int = 115200) -> dict:
    return session.log.connect(port=port, baudrate=baudrate)


def disconnect_log(session: SessionState) -> dict:
    return session.log.disconnect()


def tail_logs(session: SessionState, line_count: int = 50) -> dict:
    lines = session.log.read_recent(line_count=line_count)
    last_meaningful = next((line for line in reversed(lines) if line.strip()), None)
    return {
        "status": "ok",
        "summary": f"Read {len(lines)} recent UART log lines.",
        "lines": lines,
        "last_meaningful_line": last_meaningful,
    }
