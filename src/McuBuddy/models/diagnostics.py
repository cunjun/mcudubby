from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FaultRegisters(BaseModel):
    pc: str | None = None
    lr: str | None = None
    sp: str | None = None
    xpsr: str | None = None
    cfsr: str | None = None
    hfsr: str | None = None
    mmfar: str | None = None
    bfar: str | None = None
    shcsr: str | None = None


class SymbolContext(BaseModel):
    pc_symbol: str | None = None
    lr_symbol: str | None = None
    source: str | dict[str, Any] | None = None


class LogContext(BaseModel):
    included: bool = False
    last_lines: list[str] = Field(default_factory=list)
    last_meaningful_line: str | None = None
    log_stopped_abruptly: bool = False


class StackSnapshot(BaseModel):
    included: bool = False
    start_address: str | None = None
    size_bytes: int = 0
    data_hex: str | None = None


class HardFaultDiagnosis(BaseModel):
    status: str
    diagnosis_type: str
    summary: str
    confidence: str
    target_state: dict[str, Any]
    fault: dict[str, Any]
    symbol_context: SymbolContext
    log_context: LogContext
    stack_snapshot: StackSnapshot
    evidence: list[str] = Field(default_factory=list)
    raw_refs: dict[str, Any] = Field(default_factory=dict)
