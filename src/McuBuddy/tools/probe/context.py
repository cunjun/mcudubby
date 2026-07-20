from __future__ import annotations

from ...session import SessionState


def read_stopped_context(
    session: SessionState,
    include_fault_registers: bool = True,
    include_logs: bool = False,
    log_tail_lines: int = 20,
    resolve_symbols: bool = True,
) -> dict:
    core = session.probe.read_core_registers()
    fault = session.probe.read_fault_registers() if include_fault_registers else {}

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

    return {
        "status": "ok",
        "summary": "Read stopped target context.",
        "state": session.probe.get_state(),
        "registers": {
            "pc": hex(core["pc"]),
            "lr": hex(core["lr"]),
            "sp": hex(core["sp"]),
            "xpsr": hex(core["xpsr"]),
            **{name: hex(value) for name, value in fault.items()},
        },
        "symbol_context": {
            "pc_symbol": pc_symbol,
            "lr_symbol": lr_symbol,
            "source": source,
        },
        "log_context": {
            "included": include_logs,
            "last_lines": log_lines,
            "last_meaningful_line": last_meaningful,
        },
    }


def step_instruction(session: SessionState) -> dict:
    result = session.probe.step()
    pc_hex = result.get("pc")
    if pc_hex and session.elf.is_loaded:
        resolved = session.elf.resolve_address(int(pc_hex, 16))
        result["symbol"] = resolved["symbol"]
        result["source"] = resolved["source"]
    return result
