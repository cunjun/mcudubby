from __future__ import annotations

from typing import Literal

from ..session import SessionState

_MAX_UART_TIMEOUT_MS = 60_000
_MAX_UART_READ_BYTES = 1024 * 1024
_MAX_UART_WRITE_BYTES = 64 * 1024


def connect_log(session: SessionState, port: str, baudrate: int = 115200) -> dict:
    return session.log.connect(port=port, baudrate=baudrate)


def disconnect_log(session: SessionState) -> dict:
    return session.log.disconnect()


def uart_send(
    session: SessionState,
    data: str,
    data_format: Literal["hex", "text"],
) -> dict:
    payload = _encode_uart_data(data, data_format)

    bytes_sent = session.log.write(payload)
    return {
        "status": "ok",
        "summary": f"Sent {bytes_sent} byte(s) over UART.",
        "data_format": data_format,
        "bytes_sent": bytes_sent,
        "payload_hex": payload.hex(" "),
    }


def uart_read_bytes(
    session: SessionState,
    *,
    timeout_ms: int = 1000,
    max_bytes: int = 4096,
    idle_timeout_ms: int = 50,
) -> dict:
    _validate_uart_read_limits(timeout_ms, max_bytes, idle_timeout_ms)
    payload, evidence = _read_uart_evidence(
        session,
        timeout_ms=timeout_ms,
        max_bytes=max_bytes,
        idle_timeout_ms=idle_timeout_ms,
    )
    return {
        "status": "ok",
        "summary": f"Read {len(payload)} byte(s) from UART.",
        "rx_hex": payload.hex(" "),
        "rx_bytes": len(payload),
        **evidence,
    }


def _read_uart_evidence(
    session: SessionState,
    *,
    timeout_ms: int,
    max_bytes: int,
    idle_timeout_ms: int,
) -> tuple[bytes, dict]:
    evidence = session.log.read_bytes(
        max_bytes=max_bytes,
        timeout_ms=timeout_ms,
        idle_timeout_ms=idle_timeout_ms,
    )
    payload = evidence.pop("data")
    return payload, evidence


def uart_exchange(
    session: SessionState,
    *,
    data: str,
    data_format: Literal["hex", "text"],
    timeout_ms: int = 1000,
    max_bytes: int = 4096,
    idle_timeout_ms: int = 50,
) -> dict:
    _validate_uart_read_limits(timeout_ms, max_bytes, idle_timeout_ms)
    payload = _encode_uart_data(data, data_format)
    bytes_sent = session.log.write(payload)
    response, evidence = _read_uart_evidence(
        session,
        timeout_ms=timeout_ms,
        max_bytes=max_bytes,
        idle_timeout_ms=idle_timeout_ms,
    )
    return {
        "status": "ok",
        "summary": f"Sent {bytes_sent} byte(s) and read {len(response)} byte(s) over UART.",
        "data_format": data_format,
        "tx_hex": payload.hex(" "),
        "tx_bytes": bytes_sent,
        "rx_hex": response.hex(" "),
        "rx_bytes": len(response),
        **evidence,
    }


def _encode_uart_data(data: str, data_format: str) -> bytes:
    if not data:
        raise ValueError("data must not be empty")
    if data_format == "hex":
        try:
            payload = bytes.fromhex(data)
        except ValueError as exc:
            raise ValueError("data must contain valid hexadecimal bytes") from exc
        if not payload:
            raise ValueError("data must not be empty")
        return _validate_uart_payload(payload)
    if data_format == "text":
        return _validate_uart_payload(data.encode("utf-8"))
    raise ValueError("data_format must be 'hex' or 'text'")


def _validate_uart_payload(payload: bytes) -> bytes:
    if len(payload) > _MAX_UART_WRITE_BYTES:
        raise ValueError(f"UART payload must not exceed {_MAX_UART_WRITE_BYTES} bytes")
    return payload


def _validate_uart_read_limits(
    timeout_ms: int, max_bytes: int, idle_timeout_ms: int
) -> None:
    if timeout_ms > _MAX_UART_TIMEOUT_MS:
        raise ValueError(f"timeout_ms must not exceed {_MAX_UART_TIMEOUT_MS}")
    if idle_timeout_ms > _MAX_UART_TIMEOUT_MS:
        raise ValueError(f"idle_timeout_ms must not exceed {_MAX_UART_TIMEOUT_MS}")
    if max_bytes > _MAX_UART_READ_BYTES:
        raise ValueError(f"max_bytes must not exceed {_MAX_UART_READ_BYTES}")


def tail_logs(session: SessionState, line_count: int = 50) -> dict:
    lines = session.log.read_recent(line_count=line_count)
    last_meaningful = next((line for line in reversed(lines) if line.strip()), None)
    return {
        "status": "ok",
        "summary": f"Read {len(lines)} recent UART log lines.",
        "lines": lines,
        "last_meaningful_line": last_meaningful,
    }
