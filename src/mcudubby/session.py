from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .backends.log.uart_backend import UartLogBackend
from .backends.probe.jlink_backend import JLinkProbeBackend
from .backends.probe.base import ProbeBackend
from .backends.probe.pyocd_backend import PyOcdProbeBackend
from .backends.probe.probe_rs_backend import ProbeRsBackend
from .build_runtime import KeilBuildRuntime
from .config import RuntimeConfig
from .elf_manager import ElfManager
from .gdb_server import GdbServerRuntime
from .svd_manager import SvdManager


class LogBackend(Protocol):
    def connect(self, port: str, baudrate: int = 115200) -> dict[str, Any]: ...

    def disconnect(self) -> dict[str, Any]: ...

    def read_recent(self, line_count: int = 50) -> list[str]: ...


class ElfBackend(Protocol):
    @property
    def is_loaded(self) -> bool: ...

    def load(self, path: str) -> dict[str, Any]: ...

    def resolve_address(self, address: int) -> dict[str, Any]: ...

    def resolve_symbol(self, name: str) -> dict[str, Any]: ...

    def addr_to_source(self, address: int) -> dict[str, Any]: ...

    def source_to_addrs(self, filename: str, line: int) -> list[int]: ...

    def get_locals_at(self, pc: int) -> list[dict[str, Any]]: ...

    def get_section_data(self) -> list[dict[str, Any]]: ...

    def get_sections(self) -> list[dict[str, Any]]: ...

    def list_functions(self, name_filter: str | None = None) -> list[dict[str, Any]]: ...

    def symbol_info(self, name: str) -> dict[str, Any]: ...

    def get_cfi_at(self, pc: int) -> dict[str, Any] | None: ...


class SvdBackend(Protocol):
    _peripheral_map: dict[str, Any]

    @property
    def is_loaded(self) -> bool: ...

    def load(self, path: str) -> dict[str, Any]: ...

    def list_peripherals(self) -> dict[str, Any]: ...

    def get_peripheral_registers(self, peripheral_name: str) -> dict[str, Any]: ...

    def read_peripheral_state(
        self, peripheral_name: str, probe: ProbeBackend
    ) -> dict[str, Any]: ...

    def write_register(
        self,
        peripheral_name: str,
        register_name: str,
        value: int,
        probe: ProbeBackend,
    ) -> dict[str, Any]: ...

    def write_field(
        self,
        peripheral_name: str,
        register_name: str,
        field_name: str,
        value: int,
        probe: ProbeBackend,
    ) -> dict[str, Any]: ...


class BuildRuntimeBackend(Protocol):
    def build(self, build: Any, elf: Any, timeout_seconds: int = 120) -> dict[str, Any]: ...

    def flash(self, build: Any, elf: Any, timeout_seconds: int = 120) -> dict[str, Any]: ...


def create_probe_backend(
    name: str,
    jlink_dll_path: str | None = None,
    probe_rs_sidecar_path: str | None = None,
) -> ProbeBackend:
    if name == "pyocd":
        return PyOcdProbeBackend()
    if name == "jlink":
        return JLinkProbeBackend(dll_path=jlink_dll_path)
    if name == "probe-rs":
        return ProbeRsBackend(sidecar_path=probe_rs_sidecar_path)
    raise ValueError(f"Unknown probe backend: {name}")


@dataclass(slots=True)
class SessionState:
    probe: ProbeBackend = field(default_factory=PyOcdProbeBackend)
    log: LogBackend = field(default_factory=UartLogBackend)
    elf: ElfBackend = field(default_factory=ElfManager)
    svd: SvdBackend = field(default_factory=SvdManager)
    build: BuildRuntimeBackend = field(default_factory=KeilBuildRuntime)
    gdb_server: GdbServerRuntime = field(default_factory=GdbServerRuntime)
    config: RuntimeConfig = field(default_factory=RuntimeConfig)
    memory_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    conditional_breakpoints: dict[int, dict[str, Any]] = field(default_factory=dict)


def create_default_session() -> SessionState:
    session = SessionState()
    session.probe = create_probe_backend(
        session.config.probe.backend,
        jlink_dll_path=session.config.probe.jlink_dll_path,
        probe_rs_sidecar_path=session.config.probe.probe_rs_sidecar_path,
    )
    return session
