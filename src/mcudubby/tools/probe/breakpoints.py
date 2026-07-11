from __future__ import annotations

from ...session import SessionState
from ...tool_safety import require_tool_confirmation
from .conditions import _OPS, _evaluate_condition
from .source import _resolve_breakpoint_address


def set_breakpoint(
    session: SessionState,
    symbol: str | None = None,
    address: int | None = None,
    condition_symbol: str | None = None,
    condition_register: str | None = None,
    condition_op: str = "eq",
    condition_value: int = 0,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("set_breakpoint", confirm):
        return blocked
    if (condition_symbol or condition_register) and condition_op not in _OPS:
        return {
            "status": "error",
            "summary": f"Invalid condition_op '{condition_op}'. Use one of: {', '.join(sorted(_OPS))}.",
        }
    resolved_symbol = None
    resolved_address = _resolve_breakpoint_address(session, symbol=symbol, address=address)
    if symbol and session.elf.is_loaded:
        resolved_symbol = symbol

    result = session.probe.set_breakpoint(resolved_address)
    result["breakpoint"] = {
        "symbol": resolved_symbol,
        "address": hex(resolved_address),
    }

    if condition_symbol or condition_register:
        cond: dict = {
            "symbol": resolved_symbol,
            "address": hex(resolved_address),
            "condition_symbol": condition_symbol,
            "condition_register": condition_register,
            "condition_op": condition_op,
            "condition_value": condition_value,
        }
        session.conditional_breakpoints[resolved_address] = cond
        result["conditional"] = True
        result["condition"] = cond
        cond_target = (
            f"symbol {condition_symbol}" if condition_symbol else f"register {condition_register}"
        )
        result["summary"] = (
            f"Conditional breakpoint set at {resolved_symbol or hex(resolved_address)}: "
            f"{cond_target} {condition_op} {hex(condition_value)}."
        )
    elif resolved_symbol:
        result["summary"] = f"Breakpoint set at {resolved_symbol}."

    return result


def clear_breakpoint(
    session: SessionState,
    symbol: str | None = None,
    address: int | None = None,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("clear_breakpoint", confirm):
        return blocked
    resolved_address = _resolve_breakpoint_address(session, symbol=symbol, address=address)
    result = session.probe.clear_breakpoint(resolved_address)
    result["breakpoint"] = {
        "symbol": symbol,
        "address": hex(resolved_address),
    }
    session.conditional_breakpoints.pop(resolved_address, None)
    if symbol:
        result["summary"] = f"Breakpoint cleared at {symbol}."
    return result


def clear_all_breakpoints(session: SessionState, confirm: bool = False) -> dict:
    if blocked := require_tool_confirmation("clear_all_breakpoints", confirm):
        return blocked
    if hasattr(session, "conditional_breakpoints"):
        session.conditional_breakpoints.clear()
    return session.probe.clear_all_breakpoints()


def list_conditional_breakpoints(session: SessionState) -> dict:
    entries = list(session.conditional_breakpoints.values())
    return {
        "status": "ok",
        "summary": f"{len(entries)} conditional breakpoint(s) registered.",
        "conditional_breakpoints": entries,
    }


def continue_target(
    session: SessionState,
    timeout_seconds: float = 5.0,
    poll_interval_ms: int = 50,
    max_condition_loops: int = 1000,
) -> dict:
    for loop in range(max_condition_loops):
        result = session.probe.continue_target(
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=max(poll_interval_ms, 1) / 1000.0,
        )
        pc_hex = result.get("pc")
        if pc_hex and session.elf.is_loaded:
            resolved = session.elf.resolve_address(int(pc_hex, 16))
            result["symbol"] = resolved["symbol"]
            result["source"] = resolved["source"]

        if pc_hex and getattr(session, "conditional_breakpoints", None):
            pc = int(pc_hex, 16) & ~1
            cond = session.conditional_breakpoints.get(pc)
            if cond and not _evaluate_condition(session, cond):
                result["_condition_skipped"] = True
                continue

        if loop > 0:
            result["condition_skip_count"] = loop
        return result

    result["summary"] = f"Stopped after {max_condition_loops} conditional breakpoint skips."
    result["condition_skip_limit_reached"] = True
    return result
