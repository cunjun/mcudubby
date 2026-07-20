from __future__ import annotations

import base64
import time
from typing import Any

from .base import ProbeBackend
from .sidecar_client import SidecarProtocolError, SidecarRpcClient


class ProbeRsBackend(ProbeBackend):
    """probe-rs backend served by the bundled Rust sidecar."""

    CAPABILITIES = ProbeBackend.CAPABILITIES

    def __init__(
        self,
        sidecar_path: str | None = None,
        client: SidecarRpcClient | None = None,
    ) -> None:
        self._sidecar_path = sidecar_path
        self._client = client
        self._handshake_complete = False
        self._session_id: str | None = None
        self._breakpoints: set[int] = set()

    def _rpc(self) -> Any:
        if self._client is None:
            self._client = SidecarRpcClient.start(self._sidecar_path)
        if not self._handshake_complete:
            hello = self._client.call(
                "hello", {"client": "McuBubby", "protocol_version": 1}
            )
            if hello.get("protocol_version") != 1:
                raise RuntimeError("probe-rs sidecar protocol version is incompatible")
            self._handshake_complete = True
        return self._client

    def _session_params(self, **params: Any) -> dict[str, Any]:
        if self._session_id is None:
            raise RuntimeError("Probe is not connected")
        return {"session_id": self._session_id, **params}

    def enumerate_probes(self) -> list[dict[str, Any]]:
        return list(self._rpc().call("list_probes"))

    def connect(self, target: str, unique_id: str | None = None) -> dict[str, Any]:
        result = self._rpc().call(
            "connect", {"target": target, "unique_id": unique_id}
        )
        self._session_id = result["session_id"]
        return {
            "status": "ok",
            "summary": f"Connected to {result.get('target', target)} through probe-rs.",
            **result,
        }

    def disconnect(self) -> dict[str, Any]:
        if self._session_id is None:
            self.close()
            return {"status": "ok", "summary": "Probe was already disconnected."}
        result = self._rpc().call("disconnect", self._session_params())
        self._session_id = None
        self._breakpoints.clear()
        self.close()
        return {"status": "ok", "summary": "Disconnected probe-rs session.", **result}

    def halt(self) -> dict[str, Any]:
        return self._status_result("halt", "Halted target.")

    def resume(self) -> dict[str, Any]:
        return self._status_result("resume", "Resumed target.")

    def reset(self, halt: bool = False) -> dict[str, Any]:
        result = self._rpc().call("reset", self._session_params(halt=halt))
        return {"status": "ok", "summary": "Reset target.", **result}

    def step(self) -> dict[str, Any]:
        return self._status_result("step", "Stepped target.")

    def _status_result(self, method: str, summary: str) -> dict[str, Any]:
        result = self._rpc().call(method, self._session_params())
        return {"status": "ok", "summary": summary, **result}

    def get_state(self) -> str:
        result = self._rpc().call("get_state", self._session_params())
        return str(result["state"])

    def continue_target(
        self,
        timeout_seconds: float = 5.0,
        poll_interval_seconds: float = 0.05,
    ) -> dict[str, Any]:
        self.resume()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            state = self.get_state()
            if state != "running":
                registers = self.read_core_registers()
                return {
                    "status": "ok",
                    "summary": "Target stopped.",
                    "state": state,
                    "stop_reason": "target_stopped",
                    "pc": hex(registers["pc"]),
                }
            time.sleep(poll_interval_seconds)
        self.halt()
        registers = self.read_core_registers()
        return {
            "status": "ok",
            "summary": "Timed out waiting for target to stop; target halted.",
            "state": "halted",
            "stop_reason": "timeout",
            "pc": hex(registers["pc"]),
        }

    def read_core_registers(self) -> dict[str, int]:
        result = self._rpc().call("read_core_registers", self._session_params())
        return {name: int(value) for name, value in result["registers"].items()}

    def read_fault_registers(self) -> dict[str, int]:
        registers = {
            "cfsr": 0xE000ED28,
            "hfsr": 0xE000ED2C,
            "dfsr": 0xE000ED30,
            "mmfar": 0xE000ED34,
            "bfar": 0xE000ED38,
            "afsr": 0xE000ED3C,
        }
        return {
            name: int.from_bytes(self.read_memory(address, 4), "little")
            for name, address in registers.items()
        }

    def read_memory(self, address: int, size: int) -> bytes:
        result = self._rpc().call(
            "read_memory", self._session_params(address=address, size=size)
        )
        data = base64.b64decode(result["data_base64"], validate=True)
        if len(data) != size:
            raise SidecarProtocolError(
                f"sidecar returned {len(data)} byte(s) for a {size}-byte read"
            )
        return data

    def write_memory(self, address: int, data: bytes) -> None:
        result = self._rpc().call(
            "write_memory",
            self._session_params(
                address=address,
                data_base64=base64.b64encode(data).decode("ascii"),
            ),
        )
        if result.get("bytes_written") != len(data):
            raise SidecarProtocolError(
                f"sidecar wrote {result.get('bytes_written')} byte(s) for a {len(data)}-byte write"
            )

    def set_breakpoint(self, address: int) -> dict[str, Any]:
        result = self._rpc().call(
            "set_breakpoint", self._session_params(address=address)
        )
        self._breakpoints.add(address)
        return {"status": "ok", "summary": f"Set breakpoint at {hex(address)}.", **result}

    def clear_breakpoint(self, address: int) -> dict[str, Any]:
        result = self._rpc().call(
            "clear_breakpoint", self._session_params(address=address)
        )
        self._breakpoints.discard(address)
        return {"status": "ok", "summary": f"Cleared breakpoint at {hex(address)}.", **result}

    def clear_all_breakpoints(self) -> dict[str, Any]:
        cleared_count = len(self._breakpoints)
        for address in list(self._breakpoints):
            self.clear_breakpoint(address)
        return {
            "status": "ok",
            "summary": "Cleared all tracked breakpoints.",
            "cleared_count": cleared_count,
        }

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._handshake_complete = False
