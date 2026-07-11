from __future__ import annotations

from ...session import SessionState
from ...tool_safety import require_tool_confirmation


def get_locals(session: SessionState) -> dict:
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded. Load an ELF file first."}
    core = session.probe.read_core_registers()
    pc = core["pc"]
    variables = session.elf.get_locals_at(pc)
    if not variables:
        return {
            "status": "ok",
            "summary": "No local variable info at current PC (no DWARF or optimized out).",
            "pc": hex(pc),
            "variables": [],
        }
    result: list[dict] = []
    for var in variables:
        entry: dict = {
            "name": var["name"],
            "type": var["type_name"],
            "byte_size": var["byte_size"],
            "value": None,
            "hex": None,
            "note": None,
        }
        try:
            size = max(1, min(var["byte_size"], 8))
            loc_type = var["loc_type"]
            loc_value = var["loc_value"]
            data: bytes | None = None

            if loc_type == "addr":
                data = session.probe.read_memory(loc_value, size)
            elif loc_type == "fbreg":
                data = session.probe.read_memory(core["sp"] + loc_value, size)
            elif loc_type == "reg":
                reg_val = core.get(loc_value)
                if reg_val is not None:
                    data = reg_val.to_bytes(4, "little")
            elif loc_type == "breg":
                reg_name, offset = loc_value
                reg_val = core.get(reg_name)
                if reg_val is not None:
                    data = session.probe.read_memory(reg_val + offset, size)
            else:
                entry["note"] = "location unknown (optimized out or complex expression)"

            if data:
                int_val = int.from_bytes(data[: min(size, 4)], "little")
                entry["value"] = int_val
                entry["hex"] = hex(int_val)
        except Exception as e:
            entry["note"] = str(e)
        result.append(entry)

    src = session.elf.addr_to_source(pc)
    return {
        "status": "ok",
        "summary": f"Found {len(result)} local variable(s) at {hex(pc)}.",
        "pc": hex(pc),
        "source": f"{src['file']}:{src['line']}" if src["file"] else None,
        "variables": result,
    }


def set_local(session: SessionState, name: str, value: int, confirm: bool = False) -> dict:
    if blocked := require_tool_confirmation("set_local", confirm):
        return blocked
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded. Load an ELF file first."}
    core = session.probe.read_core_registers()
    pc = core["pc"]
    variables = session.elf.get_locals_at(pc)
    var = next((v for v in variables if v["name"] == name), None)
    if var is None:
        names = [v["name"] for v in variables]
        return {
            "status": "error",
            "summary": f"Variable '{name}' not found at current PC.",
            "available": names,
        }
    size = max(1, min(var["byte_size"], 4))
    try:
        raw = value.to_bytes(size, "little")
    except OverflowError:
        return {"status": "error", "summary": f"Value {value} does not fit in {size} byte(s)."}

    loc_type = var["loc_type"]
    loc_value = var["loc_value"]
    try:
        if loc_type == "addr":
            session.probe.write_memory(loc_value, raw)
        elif loc_type == "fbreg":
            session.probe.write_memory(core["sp"] + loc_value, raw)
        elif loc_type == "breg":
            reg_name, offset = loc_value
            reg_val = core.get(reg_name)
            if reg_val is None:
                return {"status": "error", "summary": f"Register '{reg_name}' not available."}
            session.probe.write_memory(reg_val + offset, raw)
        elif loc_type == "reg":
            return {
                "status": "error",
                "summary": f"'{name}' lives in a register; use probe_write_memory to patch register state.",
            }
        else:
            return {
                "status": "error",
                "summary": f"'{name}' has unknown location (optimized out or complex expression).",
            }
    except Exception as e:
        return {"status": "error", "summary": str(e)}

    return {
        "status": "ok",
        "summary": f"Wrote {hex(value)} to local '{name}' ({var['type_name']}).",
        "name": name,
        "type": var["type_name"],
        "value": hex(value),
        "address": hex(core["sp"] + loc_value)
        if loc_type == "fbreg"
        else hex(loc_value)
        if loc_type == "addr"
        else None,
    }
