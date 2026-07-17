from __future__ import annotations

from ...session import SessionState
from ...tool_safety import require_tool_confirmation
from .breakpoint_lifecycle import temporary_breakpoint


def addr_to_source(session: SessionState, address: int) -> dict:
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded. Load an ELF file first."}

    src = session.elf.addr_to_source(address)
    sym = session.elf.resolve_address(address)
    return {
        "status": "ok",
        "address": hex(address),
        "file": src["file"],
        "line": src["line"],
        "source": sym["source"],
        "symbol": sym["symbol"],
    }


def run_to_source(
    session: SessionState,
    file: str,
    line: int,
    timeout_seconds: float = 10.0,
) -> dict:
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded. Load an ELF file first."}
    addrs = session.elf.source_to_addrs(file, line)
    if not addrs:
        return {
            "status": "error",
            "summary": f"No address found for {file}:{line}. Check file name and line number.",
        }
    target_addr = addrs[0]
    with temporary_breakpoint(session.probe, target_addr):
        result = session.probe.continue_target(
            timeout_seconds=timeout_seconds, poll_interval_seconds=0.05
        )
    new_pc = int(result.get("pc", hex(target_addr)), 16)
    src = session.elf.addr_to_source(new_pc)
    sym = session.elf.resolve_address(new_pc)["symbol"]
    return {
        "status": "ok",
        "summary": f"Ran to {file}:{line}.",
        "pc": hex(new_pc),
        "source": f"{src['file']}:{src['line']}" if src["file"] else None,
        "symbol": sym,
        "stop_reason": result.get("stop_reason"),
    }


def run_to_function(
    session: SessionState,
    name: str,
    timeout_seconds: float = 10.0,
) -> dict:
    try:
        if session.elf.is_loaded:
            resolved = session.elf.resolve_symbol(name)
            if resolved["address"] is None:
                return {"status": "error", "summary": f"Symbol '{name}' not found in ELF."}
        else:
            return {"status": "error", "summary": "ELF not loaded."}

        addr = int(resolved["address"], 16) & ~1
        with temporary_breakpoint(session.probe, addr):
            result = session.probe.continue_target(
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=0.05,
            )

        new_pc = int(result.get("pc", hex(addr)), 16)
        if session.elf.is_loaded:
            src = session.elf.addr_to_source(new_pc)
            sym = session.elf.resolve_address(new_pc).get("symbol")
        else:
            src = {"file": None, "line": None}
            sym = None
        return {
            "status": "ok",
            "summary": f"Ran to function '{name}' at {hex(new_pc)}.",
            "function": name,
            "address": hex(addr),
            "pc": hex(new_pc),
            "stop_reason": result.get("stop_reason"),
            "symbol": sym,
            "source": f"{src['file']}:{src['line']}" if src["file"] else None,
        }
    except Exception as e:
        return {"status": "error", "summary": str(e)}


def set_breakpoints_for_function_range(
    session: SessionState,
    start_symbol: str,
    end_symbol: str,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("set_breakpoints_for_function_range", confirm):
        return blocked
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded."}

    start_resolved = session.elf.resolve_symbol(start_symbol)
    if start_resolved["address"] is None:
        return {"status": "error", "summary": f"Symbol '{start_symbol}' not found in ELF."}

    end_resolved = session.elf.resolve_symbol(end_symbol)
    if end_resolved["address"] is None:
        return {"status": "error", "summary": f"Symbol '{end_symbol}' not found in ELF."}

    start_addr = int(start_resolved["address"], 16)
    end_addr = int(end_resolved["address"], 16)
    functions = session.elf.list_functions()
    selected = [func for func in functions if start_addr <= int(func["address"], 16) < end_addr]

    set_list: list[dict[str, str]] = []
    failed_list: list[dict[str, str]] = []
    for func in selected:
        func_addr = int(func["address"], 16) & ~1
        try:
            session.probe.set_breakpoint(func_addr)
            set_list.append({"name": func["name"], "address": hex(func_addr)})
        except Exception as e:
            failed_list.append({"name": func["name"], "address": hex(func_addr), "error": str(e)})

    return {
        "status": "ok",
        "summary": f"Set {len(set_list)} breakpoint(s) between {start_symbol} and {end_symbol}.",
        "set": set_list,
        "failed": failed_list,
    }


def _resolve_breakpoint_address(
    session: SessionState,
    symbol: str | None = None,
    address: int | None = None,
) -> int:
    if address is not None:
        return int(address) & ~1
    if symbol is None:
        raise ValueError("either symbol or address must be provided")
    if not session.elf.is_loaded:
        raise ValueError("ELF symbols must be loaded before using symbol breakpoints")

    resolved = session.elf.resolve_symbol(symbol)
    if resolved["address"] is None:
        raise ValueError(f"symbol '{symbol}' could not be resolved")
    return int(resolved["address"], 16) & ~1
