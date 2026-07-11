from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..session import SessionState


@dataclass(slots=True)
class DiagnosticContext:
    core: dict[str, int]
    fault_registers: dict[str, int]
    pc_symbol: str | None
    lr_symbol: str | None
    source: str | None
    log_lines: list[str]
    last_meaningful_log: str | None
    raw_refs: dict[str, Any]


def collect_diagnostic_context(
    session: SessionState,
    include_fault_registers: bool = True,
    include_logs: bool = True,
    log_tail_lines: int = 50,
    resolve_symbols: bool = True,
) -> DiagnosticContext:
    core = session.probe.read_core_registers()
    fault_registers = session.probe.read_fault_registers() if include_fault_registers else {}

    pc_symbol = None
    lr_symbol = None
    source = None
    if resolve_symbols and session.elf.is_loaded:
        pc_result = session.elf.resolve_address(core["pc"])
        lr_result = session.elf.resolve_address(core["lr"])
        pc_symbol = pc_result["symbol"]
        lr_symbol = lr_result["symbol"]
        source = pc_result["source"]

    log_lines: list[str] = []
    last_meaningful = None
    if include_logs:
        log_lines = session.log.read_recent(log_tail_lines)
        last_meaningful = next((line for line in reversed(log_lines) if line.strip()), None)

    config = getattr(session, "config", None)
    probe_config = getattr(config, "probe", None)
    log_config = getattr(config, "log", None)

    return DiagnosticContext(
        core=core,
        fault_registers=fault_registers,
        pc_symbol=pc_symbol,
        lr_symbol=lr_symbol,
        source=source,
        log_lines=log_lines,
        last_meaningful_log=last_meaningful,
        raw_refs={
            "elf_loaded": session.elf.is_loaded,
            "probe_backend": getattr(probe_config, "backend", None),
            "log_backend": getattr(log_config, "backend", None),
        },
    )
