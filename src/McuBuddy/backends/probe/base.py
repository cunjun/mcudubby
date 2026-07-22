from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar


class ProbeCapability(str, Enum):
    CORE_CONTROL = "core-control"
    CORE_REGISTERS = "core-registers"
    FAULT_REGISTERS = "fault-registers"
    MEMORY_READ = "memory-read"
    MEMORY_WRITE = "memory-write"
    BREAKPOINTS = "breakpoints"
    WATCHPOINTS = "watchpoints"
    FPU_REGISTERS = "fpu-registers"
    FLASH = "flash"
    FLASH_IMAGE = "flash-image"
    RTT_READ = "rtt-read"
    DWT_CYCLE_COUNTER = "dwt-cycle-counter"
    SWO = "swo"
    ITM_TRACE = "itm-trace"
    CONNECT_HINTS = "connect-hints"
    PACK_PATHS = "pack-paths"


_LEGACY_METHODS: dict[ProbeCapability, str] = {
    ProbeCapability.CORE_CONTROL: "halt",
    ProbeCapability.CORE_REGISTERS: "read_core_registers",
    ProbeCapability.FAULT_REGISTERS: "read_fault_registers",
    ProbeCapability.MEMORY_READ: "read_memory",
    ProbeCapability.MEMORY_WRITE: "write_memory",
    ProbeCapability.BREAKPOINTS: "set_breakpoint",
    ProbeCapability.WATCHPOINTS: "set_watchpoint",
    ProbeCapability.FPU_REGISTERS: "read_fpu_registers",
    ProbeCapability.FLASH: "program_flash",
    ProbeCapability.FLASH_IMAGE: "flash_image",
    ProbeCapability.RTT_READ: "read_rtt_log",
    ProbeCapability.DWT_CYCLE_COUNTER: "read_cycle_counter",
    ProbeCapability.SWO: "read_swo_log",
    ProbeCapability.ITM_TRACE: "read_itm_trace",
    ProbeCapability.CONNECT_HINTS: "set_connect_hints",
    ProbeCapability.PACK_PATHS: "set_pack_paths",
}


def probe_supports(probe: object, capability: ProbeCapability) -> bool:
    """Check a backend capability, with a compatibility path for lightweight test doubles."""
    declared = getattr(probe, "capabilities", None)
    if declared is not None:
        return capability in declared
    method_name = _LEGACY_METHODS[capability]
    return callable(getattr(probe, method_name, None))


class ProbeBackend(ABC):
    CAPABILITIES: ClassVar[frozenset[ProbeCapability]] = frozenset(
        {
            ProbeCapability.CORE_CONTROL,
            ProbeCapability.CORE_REGISTERS,
            ProbeCapability.FAULT_REGISTERS,
            ProbeCapability.MEMORY_READ,
            ProbeCapability.MEMORY_WRITE,
            ProbeCapability.BREAKPOINTS,
        }
    )

    @property
    def capabilities(self) -> frozenset[ProbeCapability]:
        return self.CAPABILITIES

    def supports(self, capability: ProbeCapability) -> bool:
        return capability in self.capabilities

    @property
    def breakpoint_addresses(self) -> frozenset[int]:
        """Return the breakpoints currently tracked by the backend."""
        return frozenset(getattr(self, "_breakpoints", ()))

    @classmethod
    def enumerate_probes(cls) -> list[dict[str, Any]]:
        """Return a list of connected probes visible to this backend.

        Each entry should contain at minimum 'unique_id' and 'description'.
        Backends that do not support enumeration may return an empty list.
        """
        return []

    @abstractmethod
    def connect(self, target: str, unique_id: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def halt(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def resume(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def reset(self, halt: bool = False) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def set_breakpoint(self, address: int) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def clear_breakpoint(self, address: int) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def clear_all_breakpoints(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def continue_target(
        self,
        timeout_seconds: float = 5.0,
        poll_interval_seconds: float = 0.05,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_state(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def read_core_registers(self) -> dict[str, int]:
        raise NotImplementedError

    @abstractmethod
    def read_fault_registers(self) -> dict[str, int]:
        raise NotImplementedError

    @abstractmethod
    def read_memory(self, address: int, size: int) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def write_memory(self, address: int, data: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def step(self) -> dict[str, Any]:
        raise NotImplementedError

    def set_watchpoint(self, address: int, size: int, watch_type: str) -> dict[str, Any]:
        raise NotImplementedError

    def remove_watchpoint(self, address: int) -> dict[str, Any]:
        raise NotImplementedError

    def clear_all_watchpoints(self) -> dict[str, Any]:
        raise NotImplementedError

    def read_fpu_registers(self) -> dict[str, Any]:
        raise NotImplementedError

    def erase_flash(
        self,
        start_address: int | None = None,
        end_address: int | None = None,
        chip_erase: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def program_flash(
        self,
        address: int,
        data: bytes,
        verify: bool = True,
    ) -> dict[str, Any]:
        """Program bytes without erasing; callers must ensure the range is erased first."""
        raise NotImplementedError

    def flash_image(
        self,
        address: int,
        data: bytes,
        erase_mode: str = "sector",
        verify: bool = True,
        reset_after: bool = True,
    ) -> dict[str, Any]:
        """Erase, program, verify, and optionally reset as one backend operation."""
        raise NotImplementedError

    def verify_flash(self, address: int, data: bytes) -> dict[str, Any]:
        raise NotImplementedError

    def read_rtt_log(self, channel: int = 0, max_bytes: int = 4096) -> dict[str, Any]:
        raise NotImplementedError

    def read_cycle_counter(self) -> dict[str, Any]:
        raise NotImplementedError

    def read_swo_log(
        self,
        cpu_speed_hz: int,
        swo_speed_hz: int,
        max_bytes: int = 1024,
        port_mask: int = 0x01,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def read_itm_trace(
        self,
        cpu_speed_hz: int,
        swo_speed_hz: int,
        stimulus_port: int = 0,
        max_bytes: int = 1024,
        port_mask: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def set_connect_hints(self, hints: dict[str, Any]) -> None:
        """Accept optional backend-specific connection hints."""

    def set_pack_paths(self, pack_paths: list[str]) -> None:
        """Accept optional CMSIS-Pack paths when the backend supports them."""
