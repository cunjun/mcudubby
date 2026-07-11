from __future__ import annotations

from collections import deque
from typing import Deque

from ...errors import BackendUnavailableError
from .base import LogBackend

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None


class UartLogBackend(LogBackend):
    """Simple UART log collector for v0.1."""

    def __init__(self, buffer_size: int = 500) -> None:
        self._serial = None
        self._buffer: Deque[str] = deque(maxlen=buffer_size)

    def connect(self, port: str, baudrate: int = 115200) -> dict:
        if serial is None:
            raise BackendUnavailableError("pyserial is not installed")
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=0.2)
        self._buffer.clear()
        self._serial.reset_input_buffer()
        return {
            "status": "ok",
            "summary": f"Connected UART log channel on {port} at {baudrate} baud.",
        }

    def disconnect(self) -> dict:
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._serial = None
        return {"status": "ok", "summary": "Disconnected UART log channel."}

    def poll(self, max_lines: int = 100) -> int:
        if self._serial is None:
            raise BackendUnavailableError("UART log channel is not connected")

        count = 0
        while count < max_lines and self._serial.in_waiting:
            raw = self._serial.readline()
            if not raw:
                break
            self._buffer.append(raw.decode(errors="replace").rstrip())
            count += 1
        return count

    def read_recent(self, line_count: int = 50) -> list[str]:
        if self._serial is None:
            raise BackendUnavailableError("UART log channel is not connected")
        self.poll(max_lines=max(line_count, 100))
        lines = list(self._buffer)
        return lines[-line_count:]
