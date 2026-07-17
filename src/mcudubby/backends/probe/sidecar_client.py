from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Protocol

from ...errors import BackendUnavailableError


class SidecarProtocolError(RuntimeError):
    """Raised when the probe sidecar violates or rejects the RPC protocol."""


class LineTransport(Protocol):
    def write_line(self, line: str) -> None: ...

    def read_line(self, timeout_seconds: float | None = None) -> str: ...

    def close(self) -> None: ...


def resolve_sidecar_path(configured_path: str | None = None) -> str:
    candidates = [configured_path, os.environ.get("MCUDUBBY_PROBE_SIDECAR")]
    binary_name = "mcudubby-probe-sidecar.exe" if os.name == "nt" else "mcudubby-probe-sidecar"
    candidates.append(str(Path(__file__).resolve().parent / "bin" / binary_name))
    candidates.append(shutil.which(binary_name))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise BackendUnavailableError(
        "probe-rs sidecar not found; configure probe_rs_sidecar_path or "
        "MCUDUBBY_PROBE_SIDECAR."
    )


class SidecarProcessTransport:
    def __init__(self, executable: str) -> None:
        self._process = subprocess.Popen(
            [executable],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._responses: queue.Queue[str | None] = queue.Queue(maxsize=1)
        self._reader = threading.Thread(target=self._read_responses, daemon=True)
        self._reader.start()

    def _read_responses(self) -> None:
        if self._process.stdout is None:
            self._responses.put(None)
            return
        for line in self._process.stdout:
            self._responses.put(line)
        self._responses.put(None)

    def write_line(self, line: str) -> None:
        if self._process.stdin is None:
            raise SidecarProtocolError("sidecar stdin is unavailable")
        self._process.stdin.write(line + "\n")
        self._process.stdin.flush()

    def read_line(self, timeout_seconds: float | None = None) -> str:
        try:
            line = self._responses.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise SidecarProtocolError(
                f"sidecar response timed out after {timeout_seconds:g} seconds"
            ) from exc
        if line is None:
            raise SidecarProtocolError("sidecar exited without a response")
        return line

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2)


class SidecarRpcClient:
    def __init__(self, transport: LineTransport, response_timeout_seconds: float = 10.0) -> None:
        self._transport = transport
        self._response_timeout_seconds = response_timeout_seconds
        self._next_id = 1
        self._call_lock = threading.Lock()

    @classmethod
    def start(cls, executable: str | None = None) -> SidecarRpcClient:
        return cls(SidecarProcessTransport(resolve_sidecar_path(executable)))

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        with self._call_lock:
            request_id = self._next_id
            self._next_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
            self._transport.write_line(json.dumps(request, separators=(",", ":")))
            try:
                response_line = self._transport.read_line(self._response_timeout_seconds)
                response = json.loads(response_line)
            except SidecarProtocolError:
                self._transport.close()
                raise
            except json.JSONDecodeError as exc:
                raise SidecarProtocolError(f"invalid sidecar JSON response: {exc}") from exc
            if response.get("jsonrpc") != "2.0":
                raise SidecarProtocolError("sidecar response has an invalid jsonrpc version")
            if response.get("id") != request_id:
                raise SidecarProtocolError("sidecar response id does not match request id")
            if error := response.get("error"):
                raise SidecarProtocolError(error.get("message", "sidecar request failed"))
            if "result" not in response:
                raise SidecarProtocolError("sidecar response is missing result")
            return response["result"]

    def close(self) -> None:
        self._transport.close()
