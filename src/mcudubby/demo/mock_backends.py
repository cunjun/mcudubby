from __future__ import annotations


class MockProbeBackend:
    """Deterministic probe backend for demo and local development."""

    @classmethod
    def enumerate_probes(cls) -> list[dict]:
        return [
            {
                "unique_id": "mock-probe-001",
                "description": "Mock CMSIS-DAP Probe",
                "vendor_name": "McuBubby",
                "product_name": "Mock Probe",
            }
        ]

    def __init__(self) -> None:
        self._connected = False
        self._halted = False
        self._breakpoints: set[int] = set()
        self._mock_memory: dict[int, int] = {}

    def connect(self, target: str, unique_id: str | None = None) -> dict:
        self._connected = True
        return {
            "status": "ok",
            "summary": f"Connected to mock target {target} via mock pyOCD probe.",
            "backend": "mock-pyocd",
            "target": target,
            "unique_id": unique_id,
        }

    def disconnect(self) -> dict:
        self._connected = False
        self._halted = False
        return {"status": "ok", "summary": "Disconnected mock probe session."}

    def halt(self) -> dict:
        self._require_connected()
        self._halted = True
        return {"status": "ok", "summary": "Mock target halted."}

    def resume(self) -> dict:
        self._require_connected()
        self._halted = False
        return {"status": "ok", "summary": "Mock target resumed."}

    def reset(self, halt: bool = False) -> dict:
        self._require_connected()
        self._halted = halt
        if halt:
            return {"status": "ok", "summary": "Mock target reset and halted."}
        return {"status": "ok", "summary": "Mock target reset."}

    def set_breakpoint(self, address: int) -> dict:
        self._require_connected()
        self._breakpoints.add(address)
        return {
            "status": "ok",
            "summary": f"Mock breakpoint set at {hex(address)}.",
            "address": hex(address),
        }

    def clear_breakpoint(self, address: int) -> dict:
        self._require_connected()
        self._breakpoints.discard(address)
        return {
            "status": "ok",
            "summary": f"Mock breakpoint cleared at {hex(address)}.",
            "address": hex(address),
        }

    def clear_all_breakpoints(self) -> dict:
        self._require_connected()
        cleared = len(self._breakpoints)
        self._breakpoints.clear()
        return {
            "status": "ok",
            "summary": f"Cleared {cleared} mock breakpoint(s).",
            "cleared_count": cleared,
        }

    def continue_target(
        self,
        timeout_seconds: float = 5.0,
        poll_interval_seconds: float = 0.05,
    ) -> dict:
        self._require_connected()
        self._halted = True
        pc = 0x08001234
        stop_reason = "breakpoint_hit" if self._breakpoints else "manual_halt"
        return {
            "status": "ok",
            "summary": "Mock target stopped after continue.",
            "stop_reason": stop_reason,
            "state": self.get_state(),
            "pc": hex(pc),
        }

    def get_state(self) -> str:
        self._require_connected()
        return "halted" if self._halted else "running"

    def read_core_registers(self) -> dict[str, int]:
        self._require_connected()
        return {
            "pc": 0x08001234,
            "lr": 0x08004567,
            "sp": 0x20001F80,
            "xpsr": 0x21000000,
            "r0": 0,
            "r1": 0,
            "r2": 0,
            "r3": 0,
        }

    def read_fault_registers(self) -> dict[str, int]:
        self._require_connected()
        return {
            "cfsr": 0x00008200,
            "hfsr": 0x40000000,
            "mmfar": 0x00000000,
            "bfar": 0x20010000,
            "shcsr": 0x00070000,
        }

    def read_memory(self, address: int, size: int) -> bytes:
        self._require_connected()
        pattern = bytes.fromhex("80 1F 00 20 34 12 00 08 67 45 00 08 AA BB CC DD")
        result = bytearray()
        for i in range(size):
            addr = address + i
            if addr in self._mock_memory:
                result.append(self._mock_memory[addr])
            else:
                result.append(pattern[(addr) % len(pattern)])
        return bytes(result)

    def write_memory(self, address: int, data: bytes) -> None:
        self._require_connected()
        for i, byte in enumerate(data):
            self._mock_memory[address + i] = byte

    def step(self) -> dict:
        self._require_connected()
        return {
            "status": "ok",
            "summary": "Mock: executed one instruction.",
            "pc": hex(0x08001238),
        }

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("mock probe is not connected")
