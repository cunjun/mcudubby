from __future__ import annotations


class MockLogBackend:
    """Deterministic UART log backend for demo and screenshot generation."""

    def __init__(self) -> None:
        self._connected = False
        self._lines = [
            "boot start",
            "clock init ok",
            "uart init ok",
            "sensor init...",
        ]

    def connect(self, port: str, baudrate: int = 115200) -> dict:
        self._connected = True
        return {
            "status": "ok",
            "summary": f"Connected mock UART on {port} at {baudrate} baud.",
        }

    def disconnect(self) -> dict:
        self._connected = False
        return {"status": "ok", "summary": "Disconnected mock UART log channel."}

    def read_recent(self, line_count: int = 50) -> list[str]:
        if not self._connected:
            raise RuntimeError("mock log backend is not connected")
        return self._lines[-line_count:]
