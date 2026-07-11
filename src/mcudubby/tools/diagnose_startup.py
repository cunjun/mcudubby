from __future__ import annotations

from ..models.diagnostics import LogContext, SymbolContext
from ..session import SessionState
from .diagnostic_context import collect_diagnostic_context
from .diagnose_faults import _classify_fault, _infer_stage_from_logs, _logs_indicate_startup_success


def diagnose_startup_failure(
    session: SessionState,
    auto_halt: bool = True,
    include_logs: bool = True,
    log_tail_lines: int = 50,
    resolve_symbols: bool = True,
    suspected_stage: str | None = None,
) -> dict:
    if auto_halt:
        session.probe.halt()

    context = collect_diagnostic_context(
        session,
        include_fault_registers=True,
        include_logs=include_logs,
        log_tail_lines=log_tail_lines,
        resolve_symbols=resolve_symbols,
    )
    core = context.core
    pc_samples = [core["pc"]]
    for _ in range(2):
        try:
            pc_samples.append(session.probe.read_core_registers()["pc"])
        except Exception:
            break
    fault_registers = context.fault_registers
    pc_symbol = context.pc_symbol
    lr_symbol = context.lr_symbol
    source = context.source
    log_lines = context.log_lines
    last_meaningful = context.last_meaningful_log

    fault_class = _classify_fault(fault_registers)
    fault_detected = bool(fault_registers.get("cfsr", 0) or fault_registers.get("hfsr", 0))
    stage = suspected_stage or _infer_stage_from_logs(last_meaningful)
    startup_completed = _logs_indicate_startup_success(log_lines)

    if startup_completed and not fault_detected:
        diagnosis_type = "startup_completed_normally"
        summary = f"Startup completed normally past {stage}."
        confidence = "high"
    elif fault_detected:
        diagnosis_type = "startup_failure_with_fault"
        summary = f"Startup stopped around {stage} with fault registers set."
        confidence = "high"
    else:
        diagnosis_type = "startup_failure_no_fault_confirmed"
        summary = f"Startup appears to stop around {stage} without a confirmed fault."
        confidence = "medium"

    cfsr = fault_registers.get("cfsr", 0)
    hfsr = fault_registers.get("hfsr", 0)
    mmfar = fault_registers.get("mmfar", 0)
    bfar = fault_registers.get("bfar", 0)
    ipsr = core["xpsr"] & 0x1FF

    evidence: list[str] = []
    if last_meaningful:
        evidence.append(f"Last meaningful UART line = '{last_meaningful}'.")
    if pc_symbol:
        evidence.append(f"PC symbol = {pc_symbol}.")
    if lr_symbol:
        evidence.append(f"LR symbol = {lr_symbol}.")
    if len(pc_samples) >= 2 and all(pc == pc_samples[0] for pc in pc_samples):
        evidence.append(f"PC stuck at {hex(pc_samples[0])} for {len(pc_samples)} polls.")
    else:
        evidence.append("PC samples = " + ", ".join(hex(pc) for pc in pc_samples) + ".")
    evidence.append(f"LR = {hex(core['lr'])}.")
    evidence.append(f"SP = {hex(core['sp'])}.")
    evidence.append(f"xPSR = {hex(core['xpsr'])}.")
    evidence.append(f"xPSR IPSR field = {ipsr}.")
    if source:
        evidence.append(f"Source = {source}.")
    evidence.append(f"CFSR = {hex(cfsr)}, HFSR = {hex(hfsr)}.")
    evidence.append(f"MMFAR = {hex(mmfar)}, BFAR = {hex(bfar)}.")
    if startup_completed and not fault_detected:
        evidence.append("Startup success markers present in UART logs.")
    if cfsr & 0x00000001:
        evidence.append("CFSR IACCVIOL bit set.")
    if cfsr & 0x00000002:
        evidence.append("CFSR DACCVIOL bit set.")
    if cfsr & 0x00000080:
        evidence.append(f"CFSR MMARVALID bit set, MMFAR = {hex(mmfar)}.")
    if cfsr & 0x00000100:
        evidence.append("CFSR IBUSERR bit set.")
    if cfsr & 0x00000200:
        evidence.append("CFSR PRECISERR bit set.")
    if cfsr & 0x00000400:
        evidence.append("CFSR IMPRECISERR bit set.")
    if cfsr & 0x00008000:
        evidence.append(f"CFSR BFARVALID bit set, BFAR = {hex(bfar)}.")
    if cfsr & 0x00010000:
        evidence.append("CFSR UNDEFINSTR bit set.")
    if cfsr & 0x00020000:
        evidence.append("CFSR INVSTATE bit set.")
    if cfsr & 0x00040000:
        evidence.append("CFSR INVPC bit set.")
    if cfsr & 0x00080000:
        evidence.append("CFSR NOCP bit set.")
    if cfsr & 0x01000000:
        evidence.append("CFSR UNALIGNED bit set.")
    if cfsr & 0x02000000:
        evidence.append("CFSR DIVBYZERO bit set.")
    if hfsr & 0x00000002:
        evidence.append("HFSR VECTTBL bit set.")
    if hfsr & 0x40000000:
        evidence.append("HFSR FORCED bit set.")

    return {
        "status": "ok",
        "diagnosis_type": diagnosis_type,
        "summary": summary,
        "confidence": confidence,
        "target_state": {"halted": True, "reason": "halted_for_analysis"},
        "startup_context": {
            "suspected_stage": stage,
            "last_meaningful_log": last_meaningful,
            "progress_interrupted": bool(last_meaningful) and not startup_completed,
        },
        "fault": {
            "fault_detected": fault_detected,
            "fault_class": fault_class if fault_detected else None,
            "registers": {
                "pc": hex(core["pc"]),
                "lr": hex(core["lr"]),
                "sp": hex(core["sp"]),
                "xpsr": hex(core["xpsr"]),
                **{name: hex(value) for name, value in fault_registers.items()},
            },
        },
        "symbol_context": SymbolContext(
            pc_symbol=pc_symbol,
            lr_symbol=lr_symbol,
            source=source,
        ).model_dump(),
        "log_context": LogContext(
            included=include_logs,
            last_lines=log_lines,
            last_meaningful_line=last_meaningful,
            log_stopped_abruptly=bool(last_meaningful) and not startup_completed,
        ).model_dump(),
        "evidence": evidence,
        "raw_refs": context.raw_refs,
    }
