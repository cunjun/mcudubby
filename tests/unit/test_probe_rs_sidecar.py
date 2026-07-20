from __future__ import annotations

import base64
import json
from collections import deque

import pytest

import McuBubby.tools.configuration as configuration
from McuBubby.backends.probe.base import ProbeCapability
from McuBubby.backends.probe.probe_rs_backend import ProbeRsBackend
from McuBubby.backends.probe.sidecar_client import SidecarProtocolError, SidecarRpcClient
from McuBubby.session import create_probe_backend
from McuBubby.session import SessionState
from McuBubby.tools.configuration import configure_probe


class _MemoryTransport:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = deque(json.dumps(item) for item in responses)
        self.requests: list[dict] = []
        self.read_timeouts: list[float | None] = []
        self.closed = False

    def write_line(self, line: str) -> None:
        self.requests.append(json.loads(line))

    def read_line(self, timeout_seconds: float | None = None) -> str:
        self.read_timeouts.append(timeout_seconds)
        return self.responses.popleft()

    def close(self) -> None:
        self.closed = True


def test_rpc_client_sends_versioned_request_and_returns_result() -> None:
    transport = _MemoryTransport(
        [{"jsonrpc": "2.0", "id": 1, "result": {"protocol_version": 1}}]
    )
    client = SidecarRpcClient(transport)

    result = client.call("hello", {"client": "McuBubby"})

    assert result == {"protocol_version": 1}
    assert transport.requests == [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "hello",
            "params": {"client": "McuBubby"},
        }
    ]


def test_rpc_client_applies_a_bounded_response_timeout() -> None:
    transport = _MemoryTransport([{"jsonrpc": "2.0", "id": 1, "result": {}}])
    client = SidecarRpcClient(transport, response_timeout_seconds=0.25)

    client.call("hello")

    assert transport.read_timeouts == [0.25]


def test_rpc_client_rejects_mismatched_response_id() -> None:
    client = SidecarRpcClient(
        _MemoryTransport([{"jsonrpc": "2.0", "id": 99, "result": {}}])
    )

    with pytest.raises(SidecarProtocolError, match="response id"):
        client.call("hello")


def test_rpc_client_surfaces_sidecar_error() -> None:
    client = SidecarRpcClient(
        _MemoryTransport(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32000, "message": "probe busy"},
                }
            ]
        )
    )

    with pytest.raises(SidecarProtocolError, match="probe busy"):
        client.call("connect", {"target": "STM32F103C8"})


class _FakeClient:
    def __init__(self, results: dict[str, dict | list]) -> None:
        self.results = results
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def call(self, method: str, params: dict | None = None):
        self.calls.append((method, params or {}))
        return self.results[method]

    def close(self) -> None:
        self.closed = True


def test_probe_rs_backend_declares_minimal_sidecar_capabilities() -> None:
    backend = ProbeRsBackend(client=_FakeClient({}))

    assert ProbeCapability.CORE_CONTROL in backend.capabilities
    assert ProbeCapability.CORE_REGISTERS in backend.capabilities
    assert ProbeCapability.MEMORY_READ in backend.capabilities
    assert ProbeCapability.MEMORY_WRITE in backend.capabilities
    assert ProbeCapability.BREAKPOINTS in backend.capabilities
    assert ProbeCapability.FLASH not in backend.capabilities
    assert ProbeCapability.RTT_READ not in backend.capabilities


def test_probe_rs_backend_connects_and_tracks_session() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 1, "sidecar_version": "0.1.0"},
            "connect": {"session_id": "session-1", "target": "STM32F103C8"},
        }
    )
    backend = ProbeRsBackend(client=client)

    result = backend.connect("STM32F103C8", unique_id="probe-7")

    assert result["status"] == "ok"
    assert result["session_id"] == "session-1"
    assert client.calls == [
        ("hello", {"client": "McuBubby", "protocol_version": 1}),
        ("connect", {"target": "STM32F103C8", "unique_id": "probe-7"}),
    ]


def test_probe_rs_backend_encodes_and_decodes_memory() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 1},
            "connect": {"session_id": "session-1", "target": "chip"},
            "read_memory": {"data_base64": base64.b64encode(b"\x01\x02").decode()},
            "write_memory": {"bytes_written": 2},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")

    assert backend.read_memory(0x20000000, 2) == b"\x01\x02"
    backend.write_memory(0x20000000, b"\xaa\x55")

    assert client.calls[-1] == (
        "write_memory",
        {
            "session_id": "session-1",
            "address": 0x20000000,
            "data_base64": "qlU=",
        },
    )


def test_probe_rs_backend_rejects_short_memory_response() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 1},
            "connect": {"session_id": "session-1", "target": "chip"},
            "read_memory": {"data_base64": base64.b64encode(b"\x01").decode()},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")

    with pytest.raises(SidecarProtocolError, match="returned 1 byte"):
        backend.read_memory(0x20000000, 2)


def test_probe_rs_backend_rejects_partial_memory_write() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 1},
            "connect": {"session_id": "session-1", "target": "chip"},
            "write_memory": {"bytes_written": 1},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")

    with pytest.raises(SidecarProtocolError, match="wrote 1 byte"):
        backend.write_memory(0x20000000, b"\xaa\x55")


def test_probe_rs_backend_clears_every_tracked_breakpoint() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 1},
            "connect": {"session_id": "session-1", "target": "chip"},
            "set_breakpoint": {},
            "clear_breakpoint": {},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")
    backend.set_breakpoint(0x08000100)
    backend.set_breakpoint(0x08000200)

    result = backend.clear_all_breakpoints()

    assert result["cleared_count"] == 2
    assert [call for call in client.calls if call[0] == "clear_breakpoint"] == [
        ("clear_breakpoint", {"session_id": "session-1", "address": 0x08000100}),
        ("clear_breakpoint", {"session_id": "session-1", "address": 0x08000200}),
    ]


def test_probe_rs_continue_timeout_halts_target_and_reports_context() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 1},
            "connect": {"session_id": "session-1", "target": "chip"},
            "resume": {},
            "halt": {},
            "read_core_registers": {"registers": {"pc": 0x08001234}},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")

    result = backend.continue_target(timeout_seconds=0)

    assert result == {
        "status": "ok",
        "summary": "Timed out waiting for target to stop; target halted.",
        "state": "halted",
        "stop_reason": "timeout",
        "pc": "0x8001234",
    }
    assert ("halt", {"session_id": "session-1"}) in client.calls


def test_probe_rs_backend_disconnect_closes_sidecar_process() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 1},
            "connect": {"session_id": "session-1", "target": "chip"},
            "disconnect": {"session_id": "session-1"},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")

    result = backend.disconnect()

    assert result["status"] == "ok"
    assert client.closed is True


def test_backend_factory_accepts_probe_rs_alias() -> None:
    backend = create_probe_backend("probe-rs")

    assert isinstance(backend, ProbeRsBackend)


def test_configure_probe_records_probe_rs_sidecar_path() -> None:
    session = SessionState()

    result = configure_probe(
        session,
        backend="probe-rs",
        probe_rs_sidecar_path=r"E:\tools\McuBubby-probe-sidecar.exe",
    )

    assert result["status"] == "ok"
    assert session.config.probe.backend == "probe-rs"
    assert session.config.probe.probe_rs_sidecar_path.endswith("McuBubby-probe-sidecar.exe")
    assert isinstance(session.probe, ProbeRsBackend)


def test_configure_probe_disconnects_old_backend_before_switch(monkeypatch) -> None:
    class _Backend:
        def __init__(self) -> None:
            self.disconnected = False

        def disconnect(self) -> dict:
            self.disconnected = True
            return {"status": "ok"}

    session = SessionState()
    old_backend = _Backend()
    new_backend = _Backend()
    session.probe = old_backend
    monkeypatch.setattr(configuration, "create_probe_backend", lambda *args, **kwargs: new_backend)

    result = configure_probe(session, backend="probe-rs")

    assert result["status"] == "ok"
    assert old_backend.disconnected is True
    assert session.probe is new_backend
