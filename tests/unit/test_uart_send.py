from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from McuBuddy.backends.log.uart_backend import UartLogBackend
from McuBuddy.errors import BackendUnavailableError
from McuBuddy.server import create_server
from McuBuddy.session import SessionState
from McuBuddy.tools import logs as log_tools


class _FakeSerial:
    def __init__(self, incoming: bytes = b"") -> None:
        self.writes: list[bytes] = []
        self.flush_count = 0
        self._incoming = bytearray(incoming)

    @property
    def in_waiting(self) -> int:
        return len(self._incoming)

    def read(self, size: int) -> bytes:
        data = bytes(self._incoming[:size])
        del self._incoming[:size]
        return data

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)

    def flush(self) -> None:
        self.flush_count += 1


class _FakeLog:
    def __init__(self, incoming: bytes = b"") -> None:
        self.payloads: list[bytes] = []
        self.incoming = incoming

    def write(self, data: bytes) -> int:
        self.payloads.append(data)
        return len(data)

    def read_bytes(
        self,
        *,
        max_bytes: int,
        timeout_ms: int,
        idle_timeout_ms: int,
    ) -> dict:
        data = self.incoming[:max_bytes]
        return {
            "data": data,
            "elapsed_ms": 3.5,
            "first_byte_ms": 1.0 if data else None,
            "last_byte_ms": 2.0 if data else None,
            "timed_out": not data,
            "idle_timed_out": bool(data),
        }


def test_uart_backend_writes_and_flushes_exact_bytes() -> None:
    backend = UartLogBackend()
    serial_port = _FakeSerial()
    backend._serial = serial_port

    write = getattr(backend, "write", None)
    assert write is not None

    assert write(b"\xaa\x55\x01") == 3
    assert serial_port.writes == [b"\xaa\x55\x01"]
    assert serial_port.flush_count == 1


def test_uart_backend_rejects_send_before_connect() -> None:
    backend = UartLogBackend()
    write = getattr(backend, "write", None)
    assert write is not None

    with pytest.raises(BackendUnavailableError, match="not connected"):
        write(b"\x01")


def test_uart_backend_reads_raw_bytes_without_line_decoding() -> None:
    backend = UartLogBackend()
    backend._serial = _FakeSerial(b"\xb8\x47\x00\xff")

    result = backend.read_bytes(max_bytes=16, timeout_ms=50, idle_timeout_ms=2)

    assert result["data"] == b"\xb8\x47\x00\xff"
    assert result["first_byte_ms"] is not None
    assert result["last_byte_ms"] is not None
    assert result["timed_out"] is False
    assert result["idle_timed_out"] is True


def test_uart_backend_reports_timeout_when_no_bytes_arrive() -> None:
    backend = UartLogBackend()
    backend._serial = _FakeSerial()

    result = backend.read_bytes(max_bytes=16, timeout_ms=2, idle_timeout_ms=1)

    assert result["data"] == b""
    assert result["first_byte_ms"] is None
    assert result["last_byte_ms"] is None
    assert result["timed_out"] is True
    assert result["idle_timed_out"] is False


def test_uart_backend_reports_overall_timeout_after_partial_response() -> None:
    backend = UartLogBackend()
    backend._serial = _FakeSerial(b"\xb8\x47")

    result = backend.read_bytes(max_bytes=16, timeout_ms=2, idle_timeout_ms=20)

    assert result["data"] == b"\xb8\x47"
    assert result["timed_out"] is True
    assert result["idle_timed_out"] is False


@pytest.mark.parametrize("data", ["AA 55 01", "AA5501"])
def test_uart_send_converts_hex_text_to_bytes(data: str) -> None:
    log = _FakeLog()
    send = getattr(log_tools, "uart_send", None)
    assert send is not None

    result = send(SimpleNamespace(log=log), data=data, data_format="hex")

    assert log.payloads == [b"\xaa\x55\x01"]
    assert result["status"] == "ok"
    assert result["bytes_sent"] == 3
    assert result["payload_hex"] == "aa 55 01"


def test_uart_send_encodes_text_as_utf8() -> None:
    log = _FakeLog()
    send = getattr(log_tools, "uart_send", None)
    assert send is not None

    result = send(SimpleNamespace(log=log), data="启动", data_format="text")

    assert log.payloads == ["启动".encode("utf-8")]
    assert result["bytes_sent"] == len("启动".encode("utf-8"))


@pytest.mark.parametrize(
    ("data", "data_format", "message"),
    [
        ("", "hex", "must not be empty"),
        ("   ", "hex", "must not be empty"),
        ("0", "hex", "valid hexadecimal bytes"),
        ("GG", "hex", "valid hexadecimal bytes"),
        ("", "text", "must not be empty"),
        ("hello", "binary", "data_format must be 'hex' or 'text'"),
    ],
)
def test_uart_send_rejects_invalid_input(data: str, data_format: str, message: str) -> None:
    log = _FakeLog()
    send = getattr(log_tools, "uart_send", None)
    assert send is not None

    with pytest.raises(ValueError, match=message):
        send(SimpleNamespace(log=log), data=data, data_format=data_format)

    assert log.payloads == []


def test_uart_send_is_a_confirmed_core_mcp_tool() -> None:
    session = SessionState()
    log = _FakeLog()
    session.log = log
    app = create_server(session)

    assert "uart_send" in app._tool_manager._tools
    tool = app._tool_manager.get_tool("uart_send")

    blocked = asyncio.run(tool.run({"data": "AA 55", "data_format": "hex"}))
    sent = asyncio.run(
        tool.run({"data": "AA 55", "data_format": "hex", "confirm": True})
    )

    assert blocked["status"] == "error"
    assert blocked["safety"]["level"] == "state-changing"
    assert sent["status"] == "ok"
    assert log.payloads == [b"\xaa\x55"]


def test_uart_read_bytes_returns_binary_evidence() -> None:
    log = _FakeLog(b"\xb8\x47\x00\xff")

    result = log_tools.uart_read_bytes(
        SimpleNamespace(log=log),
        timeout_ms=50,
        max_bytes=16,
        idle_timeout_ms=5,
    )

    assert result == {
        "status": "ok",
        "summary": "Read 4 byte(s) from UART.",
        "rx_hex": "b8 47 00 ff",
        "rx_bytes": 4,
        "elapsed_ms": 3.5,
        "first_byte_ms": 1.0,
        "last_byte_ms": 2.0,
        "timed_out": False,
        "idle_timed_out": True,
    }


def test_uart_exchange_writes_then_returns_raw_response() -> None:
    log = _FakeLog(b"\xb8\x47\x00\x03\x81")

    result = log_tools.uart_exchange(
        SimpleNamespace(log=log),
        data="B8 47 00 03 01 F1 D1",
        data_format="hex",
        timeout_ms=100,
        max_bytes=64,
        idle_timeout_ms=5,
    )

    assert log.payloads == [b"\xb8\x47\x00\x03\x01\xf1\xd1"]
    assert result["tx_hex"] == "b8 47 00 03 01 f1 d1"
    assert result["tx_bytes"] == 7
    assert result["rx_hex"] == "b8 47 00 03 81"
    assert result["rx_bytes"] == 5
    assert result["timed_out"] is False


def test_uart_read_and_write_limits_are_bounded() -> None:
    log = _FakeLog()
    session = SimpleNamespace(log=log)

    with pytest.raises(ValueError, match="timeout_ms must not exceed"):
        log_tools.uart_read_bytes(session, timeout_ms=60_001)
    with pytest.raises(ValueError, match="max_bytes must not exceed"):
        log_tools.uart_read_bytes(session, max_bytes=1024 * 1024 + 1)
    with pytest.raises(ValueError, match="payload must not exceed"):
        log_tools.uart_send(session, "aa" * (64 * 1024 + 1), "hex")

    assert log.payloads == []


def test_uart_binary_tools_have_core_safety_policies() -> None:
    session = SessionState()
    log = _FakeLog(b"\x81")
    session.log = log
    app = create_server(session)

    assert {"uart_read_bytes", "uart_exchange"} <= set(app._tool_manager._tools)

    read_tool = app._tool_manager.get_tool("uart_read_bytes")
    read_result = asyncio.run(read_tool.run({"timeout_ms": 5, "max_bytes": 8}))
    assert read_result["status"] == "ok"

    exchange_tool = app._tool_manager.get_tool("uart_exchange")
    blocked = asyncio.run(
        exchange_tool.run(
            {"data": "01", "data_format": "hex", "timeout_ms": 5}
        )
    )
    assert blocked["status"] == "error"
    assert blocked["safety"]["level"] == "state-changing"
