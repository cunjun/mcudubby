from __future__ import annotations

from ...session import SessionState
from ...tool_safety import require_tool_confirmation


def write_memory(
    session: SessionState,
    address: int,
    data: list[int],
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("probe_write_memory", confirm):
        return blocked
    raw = bytes(data)
    session.probe.write_memory(address, raw)
    return {
        "status": "ok",
        "summary": f"Wrote {len(raw)} byte(s) to {hex(address)}.",
        "address": hex(address),
        "length": len(raw),
    }


def read_memory(session: SessionState, address: int, size: int) -> dict:
    try:
        data = session.probe.read_memory(address, size)
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }
    return {
        "status": "ok",
        "summary": f"Read {size} byte(s) from {hex(address)}.",
        "address": hex(address),
        "size": size,
        "hex": data.hex(),
        "bytes": list(data),
        "value_u32": int.from_bytes(data[:4], "little") if size >= 4 else None,
        "value_u16": int.from_bytes(data[:2], "little") if size >= 2 else None,
        "value_u8": data[0] if size >= 1 else None,
    }


def dump_memory(
    session: SessionState,
    address: int,
    size: int = 64,
    format: str = "hex",
    columns: int = 16,
) -> dict:
    """Read and format memory. format: 'hex', 'u8', 'u16', 'u32', 'u64'."""
    try:
        data = session.probe.read_memory(address, size)
    except Exception as e:
        return {"status": "error", "summary": str(e)}

    result: dict = {
        "status": "ok",
        "summary": f"Dumped {len(data)} byte(s) from {hex(address)} as {format}.",
        "address": hex(address),
        "size": len(data),
        "format": format,
    }

    if format == "hex":
        lines = []
        cols = max(1, columns)
        for row_start in range(0, len(data), cols):
            chunk = data[row_start : row_start + cols]
            addr_str = f"{address + row_start:#010x}"
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
            padding = "   " * (cols - len(chunk))
            lines.append(f"{addr_str}  {hex_part}{padding}  |{ascii_part}|")
        result["hex_dump"] = lines
    elif format in ("u8", "u16", "u32", "u64"):
        width = {"u8": 1, "u16": 2, "u32": 4, "u64": 8}[format]
        values = []
        for i in range(0, len(data) - (len(data) % width) if width > 1 else len(data), width):
            val = int.from_bytes(data[i : i + width], "little")
            values.append(val)
        result["values"] = values
        result["values_hex"] = [hex(v) for v in values]
    else:
        return {
            "status": "error",
            "summary": f"Unknown format '{format}'. Use: hex, u8, u16, u32, u64",
        }

    return result


def memory_find(
    session: SessionState,
    address: int,
    size: int,
    pattern: list[int],
    max_results: int = 16,
) -> dict:
    try:
        data = session.probe.read_memory(address, size)
    except Exception as e:
        return {"status": "error", "summary": str(e)}

    needle = bytes(pattern)
    if not needle:
        return {"status": "error", "summary": "Pattern must not be empty."}

    matches: list[int] = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset == -1:
            break
        matches.append(offset)
        start = offset + len(needle)

    truncated = len(matches) > max_results
    visible_matches = matches[:max_results]
    pattern_bytes = [hex(b) for b in pattern]
    return {
        "status": "ok",
        "summary": f"Found {len(matches)} match(es) for pattern {pattern_bytes} in {hex(address)}+{size}.",
        "address": hex(address),
        "pattern_bytes": pattern_bytes,
        "match_count": len(matches),
        "matches": [{"address": hex(address + off), "offset": off} for off in visible_matches],
        "truncated": truncated,
    }


def step_n_instructions(session: SessionState, count: int = 10) -> dict:
    """Execute count instructions, recording PC and symbol at each step."""
    actual = max(0, min(count, 100))
    truncated = count > 100
    steps: list[dict] = []
    try:
        for i in range(actual):
            result = session.probe.step()
            pc_value = result.get("pc")
            pc = int(pc_value, 16) if isinstance(pc_value, str) else int(pc_value)
            symbol = None
            if session.elf.is_loaded:
                symbol = session.elf.resolve_address(pc).get("symbol")
            steps.append({"step": i + 1, "pc": hex(pc), "symbol": symbol})
        if steps:
            final_pc = int(steps[-1]["pc"], 16)
        else:
            final_pc = session.probe.read_core_registers()["pc"]
    except Exception as e:
        return {"status": "error", "summary": str(e)}
    return {
        "status": "ok",
        "summary": f"Stepped {actual} instruction(s). Final PC: {hex(final_pc)}.",
        "steps": steps,
        "final_pc": hex(final_pc),
        "truncated": truncated,
    }


_CORTEX_M_REGIONS = [
    {
        "name": "code",
        "start": hex(0x00000000),
        "end": hex(0x1FFFFFFF),
        "size": 0x20000000,
        "description": "Code region, including flash and aliased vector table space.",
    },
    {
        "name": "sram",
        "start": hex(0x20000000),
        "end": hex(0x3FFFFFFF),
        "size": 0x20000000,
        "description": "On-chip SRAM region.",
    },
    {
        "name": "peripherals",
        "start": hex(0x40000000),
        "end": hex(0x5FFFFFFF),
        "size": 0x20000000,
        "description": "Memory-mapped peripheral register region.",
    },
    {
        "name": "external_ram",
        "start": hex(0x60000000),
        "end": hex(0x9FFFFFFF),
        "size": 0x40000000,
        "description": "External RAM or memory controller window.",
    },
    {
        "name": "external_device",
        "start": hex(0xA0000000),
        "end": hex(0xDFFFFFFF),
        "size": 0x40000000,
        "description": "External device memory region.",
    },
    {
        "name": "system",
        "start": hex(0xE0000000),
        "end": hex(0xFFFFFFFF),
        "size": 0x20000000,
        "description": "System control space, debug blocks, NVIC, SysTick, and PPB.",
    },
]


def read_memory_map(session: SessionState) -> dict:
    """Return Cortex-M address space regions and ELF section layout (if loaded)."""
    elf_sections: list[dict] = []
    elf_sections_error = None
    if session.elf.is_loaded and hasattr(session.elf, "get_sections"):
        try:
            elf_sections = session.elf.get_sections()
        except Exception as e:
            elf_sections_error = str(e)

    summary = f"Described {len(_CORTEX_M_REGIONS)} Cortex-M memory region(s)."
    if session.elf.is_loaded:
        if elf_sections_error is None:
            summary = f"{summary} Parsed {len(elf_sections)} ELF section(s)."
        else:
            summary = f"{summary} ELF section parsing failed: {elf_sections_error}"
    return {
        "status": "ok",
        "summary": summary,
        "regions": _CORTEX_M_REGIONS,
        "elf_loaded": session.elf.is_loaded,
        "sections": elf_sections,
        "elf_sections_error": elf_sections_error,
    }


def compare_elf_to_flash(session: SessionState) -> dict:
    """Compare ELF loadable sections against target memory to verify flash contents."""
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded."}
    sections = session.elf.get_section_data()
    if not sections:
        return {"status": "error", "summary": "No loadable PROGBITS sections found in ELF."}

    results = []
    total_bytes = 0
    total_mismatches = 0
    for sec in sections:
        vma: int = sec["vma"]
        expected: bytes = sec["data"]
        size = len(expected)
        try:
            actual = session.probe.read_memory(vma, size)
        except Exception as e:
            results.append(
                {
                    "section": sec["name"],
                    "address": hex(vma),
                    "size": size,
                    "status": "read_error",
                    "error": str(e),
                }
            )
            continue
        mismatches = [
            {
                "offset": i,
                "address": hex(vma + i),
                "expected": hex(expected[i]),
                "actual": hex(actual[i]),
            }
            for i in range(size)
            if expected[i] != actual[i]
        ]
        total_bytes += size
        total_mismatches += len(mismatches)
        results.append(
            {
                "section": sec["name"],
                "address": hex(vma),
                "size": size,
                "status": "match" if not mismatches else "mismatch",
                "mismatch_count": len(mismatches),
                "mismatches": mismatches[:20],  # cap detail to first 20
            }
        )

    summary = (
        f"All {total_bytes} bytes match."
        if total_mismatches == 0
        else f"{total_mismatches} byte(s) differ across {sum(1 for r in results if r.get('mismatch_count', 0) > 0)} section(s)."
    )
    return {
        "status": "ok",
        "summary": summary,
        "total_bytes_checked": total_bytes,
        "total_mismatches": total_mismatches,
        "sections": results,
    }


def memory_snapshot(session: SessionState, address: int, size: int, label: str = "default") -> dict:
    """Capture a memory snapshot and store it under label for later diff."""
    try:
        data = session.probe.read_memory(address, size)
    except Exception as e:
        return {"status": "error", "summary": str(e)}
    session.memory_snapshots[label] = {"address": address, "size": size, "data": data}
    return {
        "status": "ok",
        "summary": f"Snapshot '{label}' taken: {size} byte(s) at {hex(address)}.",
        "label": label,
        "address": hex(address),
        "size": size,
    }


def memory_diff(session: SessionState, label: str = "default") -> dict:
    """Re-read the region from a previous snapshot and return changed bytes."""
    snap = session.memory_snapshots.get(label)
    if snap is None:
        labels = list(session.memory_snapshots.keys())
        return {
            "status": "error",
            "summary": f"No snapshot with label '{label}'.",
            "available_labels": labels,
        }
    address: int = snap["address"]
    size: int = snap["size"]
    old_data: bytes = snap["data"]

    try:
        new_data = session.probe.read_memory(address, size)
    except Exception as e:
        return {"status": "error", "summary": str(e)}

    # Find changed bytes and group into contiguous regions
    changed_bytes: list[dict] = []
    for i, (o, n) in enumerate(zip(old_data, new_data)):
        if o != n:
            changed_bytes.append(
                {
                    "address": hex(address + i),
                    "offset": i,
                    "old": hex(o),
                    "new": hex(n),
                }
            )

    # Group consecutive changed bytes into regions
    regions: list[dict] = []
    if changed_bytes:
        start = changed_bytes[0]["offset"]
        end = start
        for cb in changed_bytes[1:]:
            if cb["offset"] == end + 1:
                end = cb["offset"]
            else:
                regions.append(
                    {
                        "address": hex(address + start),
                        "offset": start,
                        "length": end - start + 1,
                        "old_hex": old_data[start : end + 1].hex(),
                        "new_hex": new_data[start : end + 1].hex(),
                    }
                )
                start = end = cb["offset"]
        regions.append(
            {
                "address": hex(address + start),
                "offset": start,
                "length": end - start + 1,
                "old_hex": old_data[start : end + 1].hex(),
                "new_hex": new_data[start : end + 1].hex(),
            }
        )

    n_changed = len(changed_bytes)
    n_regions = len(regions)
    summary = (
        f"{n_changed} byte(s) changed in {n_regions} region(s)."
        if n_changed
        else "No changes detected."
    )
    return {
        "status": "ok",
        "summary": summary,
        "label": label,
        "address": hex(address),
        "size": size,
        "total_changed_bytes": n_changed,
        "changed_regions": regions,
        "changed_bytes": changed_bytes,
    }
