from __future__ import annotations

from collections import deque
import time
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

    def write(self, data: bytes) -> int:
        if self._serial is None:
            raise BackendUnavailableError("UART log channel is not connected")
        bytes_sent = self._serial.write(data)
        self._serial.flush()
        return bytes_sent

    def read_bytes(
        self,
        *,
        max_bytes: int,
        timeout_ms: int,
        idle_timeout_ms: int,
    ) -> dict:
        if self._serial is None:
            raise BackendUnavailableError("UART log channel is not connected")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than 0")
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be greater than 0")
        if idle_timeout_ms <= 0:
            raise ValueError("idle_timeout_ms must be greater than 0")

        started = time.monotonic()
        deadline = started + timeout_ms / 1000
        received = bytearray()
        first_byte_at: float | None = None
        last_byte_at: float | None = None
        idle_timed_out = False

        while len(received) < max_bytes:
            now = time.monotonic()
            waiting = int(self._serial.in_waiting)
            if waiting:
                chunk = self._serial.read(min(waiting, max_bytes - len(received)))
                if chunk:
                    now = time.monotonic()
                    first_byte_at = first_byte_at or now
                    last_byte_at = now
                    received.extend(chunk)
                    continue
            if last_byte_at is not None and now - last_byte_at >= idle_timeout_ms / 1000:
                idle_timed_out = True
                break
            if now >= deadline:
                break
            time.sleep(0.001)

        finished = time.monotonic()
        elapsed_ms = (finished - started) * 1000
        return {
            "data": bytes(received),
            "elapsed_ms": elapsed_ms,
            "first_byte_ms": (
                (first_byte_at - started) * 1000 if first_byte_at is not None else None
            ),
            "last_byte_ms": (
                (last_byte_at - started) * 1000 if last_byte_at is not None else None
            ),
            "timed_out": finished >= deadline and len(received) < max_bytes,
            "idle_timed_out": idle_timed_out,
        }

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
