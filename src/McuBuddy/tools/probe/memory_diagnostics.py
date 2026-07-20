from __future__ import annotations

from ...session import SessionState


def diagnose_memory_corruption(
    session: SessionState,
    stack_canary: int = 0xCCCCCCCC,
) -> dict:
    """Scan stack and heap regions for corruption evidence.

    Checks: SP vs stack bounds, stack canary high-water mark, heap boundary patterns.
    stack_canary: 4-byte fill pattern used to initialize unused stack (default 0xCCCCCCCC).
    """
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded."}

    evidence: list[str] = []

    def _resolve_addr(name: str) -> int | None:
        r = session.elf.resolve_symbol(name)
        return int(r["address"], 16) if r["address"] is not None else None

    # --- Stack bounds ---
    stack_top = None
    stack_top_sym = None
    for sym in ("_estack", "__StackTop", "__stack_end__", "__stack"):
        val = _resolve_addr(sym)
        if val is not None:
            stack_top = val
            stack_top_sym = sym
            break

    stack_bottom = None
    for sym in ("__StackLimit", "__stack_start__"):
        val = _resolve_addr(sym)
        if val is not None:
            stack_bottom = val
            break

    if stack_top is not None and stack_bottom is None:
        for sym in ("_Min_Stack_Size", "__stack_size__"):
            val = _resolve_addr(sym)
            if val is not None:
                stack_bottom = stack_top - val
                break

    # --- Current SP ---
    try:
        core = session.probe.read_core_registers()
        current_sp = core["sp"]
    except Exception as e:
        return {"status": "error", "summary": f"Failed to read registers: {e}"}

    stack_info: dict = {"current_sp": hex(current_sp)}
    if stack_top is not None:
        stack_info["top_address"] = hex(stack_top)
        stack_info["top_symbol"] = stack_top_sym

    if stack_top is not None and stack_bottom is not None:
        stack_size = stack_top - stack_bottom
        stack_info["bottom_address"] = hex(stack_bottom)
        stack_info["size_bytes"] = stack_size
        sp_in_bounds = stack_bottom <= current_sp <= stack_top
        stack_info["sp_in_bounds"] = sp_in_bounds
        stack_info["sp_headroom_bytes"] = current_sp - stack_bottom
        if not sp_in_bounds:
            evidence.append(
                f"SP {hex(current_sp)} outside stack bounds [{hex(stack_bottom)}, {hex(stack_top)}]"
            )

        # Canary scan: read from bottom up, find first non-canary word
        scan_size = min(stack_size, 8192)
        try:
            raw = session.probe.read_memory(stack_bottom, scan_size)
            canary_bytes = stack_canary.to_bytes(4, "little")
            high_water: int | None = None
            for i in range(0, len(raw) - 3, 4):
                if raw[i : i + 4] != canary_bytes:
                    high_water = stack_bottom + i
                    break
            cscan: dict = {"canary_value": hex(stack_canary)}
            if high_water is not None:
                used = stack_top - high_water
                cscan["high_water_mark"] = hex(high_water)
                cscan["used_bytes_estimate"] = used
                evidence.append(
                    f"Stack high-water mark {hex(high_water)}: ~{used}/{stack_size} bytes used"
                )
            else:
                cscan["high_water_mark"] = None
                evidence.append(f"Canary intact across {scan_size} bytes from {hex(stack_bottom)}")
            stack_info["canary_scan"] = cscan
        except Exception as e:
            stack_info["canary_scan"] = {"error": str(e)}

    # --- Heap bounds ---
    heap_start: int | None = None
    heap_start_sym: str | None = None
    for sym in ("_end", "__heap_start", "__heap_start__"):
        val = _resolve_addr(sym)
        if val is not None:
            heap_start = val
            heap_start_sym = sym
            break

    heap_end: int | None = None
    for sym in ("__heap_end", "__heap_end__"):
        val = _resolve_addr(sym)
        if val is not None:
            heap_end = val
            break
    if heap_start is not None and heap_end is None:
        for sym in ("_Min_Heap_Size", "__heap_size__"):
            val = _resolve_addr(sym)
            if val is not None:
                heap_end = heap_start + val
                break

    heap_info: dict = {}
    CORRUPTION_MAGIC = {0xDEADBEEF, 0xDEADDEAD, 0xBAADF00D, 0xFEEEFEEE, 0xFDFDFDFD}
    if heap_start is not None:
        heap_info["start_address"] = hex(heap_start)
        heap_info["start_symbol"] = heap_start_sym
        if heap_end is not None:
            heap_info["end_address"] = hex(heap_end)
            heap_info["size_bytes"] = heap_end - heap_start

        # Sample first and last 16 bytes of heap for corruption patterns
        for label, addr in (("start", heap_start), ("end", heap_end - 16 if heap_end else None)):
            if addr is None:
                continue
            try:
                chunk = session.probe.read_memory(addr, 16)
                heap_info[f"{label}_16_bytes_hex"] = chunk.hex()
                if len(chunk) >= 4:
                    u32 = int.from_bytes(chunk[:4], "little")
                    if u32 in CORRUPTION_MAGIC:
                        evidence.append(
                            f"Heap {label} {hex(addr)} contains corruption magic {hex(u32)}"
                        )
            except Exception as e:
                heap_info[f"{label}_read_error"] = str(e)
    else:
        heap_info["symbols_found"] = []
        evidence.append("No heap symbols found in ELF (no _end / __heap_start)")

    parts = []
    if stack_top is not None and stack_bottom is not None:
        parts.append(f"stack [{hex(stack_bottom)}-{hex(stack_top)}]")
    if heap_start is not None:
        parts.append(f"heap from {hex(heap_start)}")
    summary = (
        f"Memory scan: {', '.join(parts)}."
        if parts
        else "Memory scan complete. No stack/heap symbols found in ELF."
    )

    return {
        "status": "ok",
        "summary": summary,
        "stack": stack_info,
        "heap": heap_info,
        "evidence": evidence,
    }
