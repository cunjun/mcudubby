from __future__ import annotations

import time

from ...session import SessionState
from ...tool_safety import require_tool_confirmation


def watch_symbol(
    session: SessionState,
    name: str,
    size: int = 4,
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.1,
) -> dict:
    """Poll a symbol's value until it changes or timeout expires."""
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded."}
    resolved = session.elf.resolve_symbol(name)
    if resolved["address"] is None:
        return {"status": "error", "summary": f"Symbol '{name}' not found in ELF."}
    addr = int(resolved["address"], 16)
    try:
        initial = session.probe.read_memory(addr, size)
    except Exception as e:
        return {"status": "error", "summary": str(e)}

    initial_int = int.from_bytes(initial[: min(size, 8)], "little")
    deadline = time.monotonic() + timeout_seconds
    polls = 0
    while time.monotonic() < deadline:
        time.sleep(poll_interval_seconds)
        polls += 1
        try:
            current = session.probe.read_memory(addr, size)
        except Exception as e:
            return {"status": "error", "summary": str(e)}
        if current != initial:
            current_int = int.from_bytes(current[: min(size, 8)], "little")
            elapsed = timeout_seconds - (deadline - time.monotonic())
            return {
                "status": "ok",
                "summary": f"Symbol '{name}' changed from {hex(initial_int)} to {hex(current_int)} after {elapsed:.2f}s.",
                "symbol": name,
                "address": hex(addr),
                "changed": True,
                "old_value": hex(initial_int),
                "new_value": hex(current_int),
                "old_bytes": initial.hex(),
                "new_bytes": current.hex(),
                "polls": polls,
                "elapsed_seconds": round(elapsed, 3),
            }
    return {
        "status": "ok",
        "summary": f"Symbol '{name}' did not change within {timeout_seconds}s ({polls} polls).",
        "symbol": name,
        "address": hex(addr),
        "changed": False,
        "value": hex(initial_int),
        "polls": polls,
    }


def elf_list_functions(session: SessionState, name_filter: str | None = None) -> dict:
    """List all function symbols from the loaded ELF."""
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded."}
    funcs = session.elf.list_functions(name_filter=name_filter)
    return {
        "status": "ok",
        "summary": f"{len(funcs)} function(s) found"
        + (f" matching '{name_filter}'." if name_filter else "."),
        "count": len(funcs),
        "functions": funcs,
    }


def elf_symbol_info(session: SessionState, name: str) -> dict:
    """Look up detailed info for a single symbol by exact name."""
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded."}
    info = session.elf.symbol_info(name)
    if not info["found"]:
        return {
            "status": "error",
            "summary": f"Symbol '{name}' not found in ELF.",
        }
    return {
        "status": "ok",
        "summary": f"Symbol '{name}' at {info['address']}, size={info['size']}.",
        **{k: v for k, v in info.items() if k != "found"},
    }


def read_symbol_value(session: SessionState, name: str, size: int = 4) -> dict:
    if not session.elf.is_loaded:
        return {
            "status": "error",
            "summary": "ELF not loaded. Load an ELF file first.",
        }
    resolved = session.elf.resolve_symbol(name)
    if resolved["address"] is None:
        return {
            "status": "error",
            "summary": f"Symbol '{name}' not found in ELF.",
        }
    addr = int(resolved["address"], 16)
    try:
        data = session.probe.read_memory(addr, size)
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }
    return {
        "status": "ok",
        "summary": f"Read symbol '{name}' at {hex(addr)}, {size} byte(s).",
        "symbol": name,
        "address": hex(addr),
        "size": size,
        "hex": data.hex(),
        "bytes": list(data),
        "value_u32": int.from_bytes(data[:4], "little") if size >= 4 else None,
        "value_u16": int.from_bytes(data[:2], "little") if size >= 2 else None,
        "value_u8": data[0] if size >= 1 else None,
    }


def write_symbol_value(
    session: SessionState,
    name: str,
    value: int,
    size: int = 4,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("write_symbol_value", confirm):
        return blocked
    if not session.elf.is_loaded:
        return {
            "status": "error",
            "summary": "ELF not loaded. Load an ELF file first.",
        }
    resolved = session.elf.resolve_symbol(name)
    if resolved["address"] is None:
        return {
            "status": "error",
            "summary": f"Symbol '{name}' not found in ELF.",
        }
    addr = int(resolved["address"], 16)
    try:
        raw = value.to_bytes(size, "little")
    except OverflowError:
        return {
            "status": "error",
            "summary": f"Value {value} does not fit in {size} byte(s).",
        }
    try:
        session.probe.write_memory(addr, raw)
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }
    return {
        "status": "ok",
        "summary": f"Wrote {hex(value)} to symbol '{name}' at {hex(addr)}, {size} byte(s).",
        "symbol": name,
        "address": hex(addr),
        "size": size,
        "value": hex(value),
    }
