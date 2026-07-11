from __future__ import annotations

from types import SimpleNamespace

from mcudubby.tools.probe import read_rtt_log


class _BackendProbe:
    def read_rtt_log(self, channel: int = 0, max_bytes: int = 4096) -> dict:
        return {
            "status": "ok",
            "summary": f"Read 5 byte(s) from J-Link RTT channel {channel}.",
            "backend": "jlink",
            "channel": channel,
            "bytes_available": 5,
            "text": "hello",
            "cb_address": None,
            "buffer_size": None,
            "wr_off": None,
            "rd_off": None,
        }


class _FallbackProbe:
    def __init__(self) -> None:
        header = (
            b"SEGGER RTT\x00".ljust(16, b"\x00")
            + (1).to_bytes(4, "little")
            + (0).to_bytes(4, "little")
        )
        self._mem = {
            0x20000000: b"xxxx" + header,
            0x20000004: header,
            0x2000001C: (0).to_bytes(4, "little")
            + (0x20000100).to_bytes(4, "little")
            + (16).to_bytes(4, "little")
            + (5).to_bytes(4, "little")
            + (0).to_bytes(4, "little")
            + (0).to_bytes(4, "little"),
            0x20000100: b"hello",
        }

    def read_rtt_log(self, channel: int = 0, max_bytes: int = 4096) -> dict:
        return {"status": "error", "summary": "backend RTT unavailable"}

    def read_memory(self, address: int, size: int) -> bytes:
        if address in self._mem:
            data = self._mem[address]
            return data[:size]
        if address == 0x20000000 and size == 20:
            return self._mem[address]
        return b"\x00" * size


def test_read_rtt_log_prefers_backend_specific_result() -> None:
    session = SimpleNamespace(probe=_BackendProbe())

    result = read_rtt_log(session, channel=0, max_bytes=32)

    assert result["status"] == "ok"
    assert result["backend"] == "jlink"
    assert result["text"] == "hello"


def test_read_rtt_log_falls_back_to_memory_scan() -> None:
    session = SimpleNamespace(probe=_FallbackProbe())

    result = read_rtt_log(
        session,
        channel=0,
        max_bytes=16,
        search_start=0x20000000,
        search_size=0x120,
    )

    assert result["status"] == "ok"
    assert result["text"] == "hello"
    assert result["backend_hint"] == "backend RTT unavailable"
