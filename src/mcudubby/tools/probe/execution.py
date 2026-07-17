from __future__ import annotations

from ...session import SessionState
from .breakpoint_lifecycle import temporary_breakpoint
from .conditions import _OPS, _evaluate_condition
from .context import step_instruction


def continue_until(
    session: SessionState,
    address: int,
    condition_symbol: str | None = None,
    condition_register: str | None = None,
    condition_op: str = "eq",
    condition_value: int = 0,
    max_hits: int = 20,
    timeout_seconds: float = 5.0,
) -> dict:
    if condition_op not in _OPS:
        return {
            "status": "error",
            "summary": f"Invalid condition_op '{condition_op}'. Use one of: {', '.join(sorted(_OPS))}.",
        }
    if condition_symbol and condition_register:
        return {
            "status": "error",
            "summary": "Provide either condition_symbol or condition_register, not both.",
        }

    target_address = int(address) & ~1
    _cond = {
        "condition_symbol": condition_symbol,
        "condition_register": condition_register,
        "condition_op": condition_op,
        "condition_value": condition_value,
    }
    has_condition = condition_symbol is not None or condition_register is not None
    try:
        with temporary_breakpoint(session.probe, target_address) as created:
            disposition = "cleared" if created else "preserved"
            for hit_count in range(1, max_hits + 1):
                result = session.probe.continue_target(
                    timeout_seconds=timeout_seconds,
                    poll_interval_seconds=0.05,
                )
                if result.get("stop_reason") == "timeout":
                    result["summary"] = (
                        f"Timed out before condition was met; breakpoint {disposition}."
                    )
                    result["condition_met"] = False
                    result["hit_count"] = hit_count - 1
                    result["breakpoint_address"] = hex(target_address)
                    return result

                core = session.probe.read_core_registers()
                pc = int(core["pc"]) & ~1
                if pc not in {target_address, target_address + 2, target_address + 4}:
                    continue

                if not has_condition or _evaluate_condition(session, _cond):
                    result.update(
                        {
                            "summary": f"Condition met at breakpoint; breakpoint {disposition}.",
                            "condition_met": True,
                            "hit_count": hit_count,
                            "breakpoint_address": hex(target_address),
                        }
                    )
                    return result

            return {
                "status": "ok",
                "summary": (
                    "Maximum breakpoint hits reached before condition was met; "
                    f"breakpoint {disposition}."
                ),
                "stop_reason": "max_hits_reached",
                "condition_met": False,
                "hit_count": max_hits,
                "breakpoint_address": hex(target_address),
            }
    except Exception as exc:
        return {
            "status": "error",
            "summary": str(exc),
            "stop_reason": "error",
            "condition_met": False,
            "breakpoint_address": hex(target_address),
        }


def read_registers(session: SessionState) -> dict:
    values = session.probe.read_core_registers()
    return {
        "status": "ok",
        "summary": "Read core registers.",
        "registers": {name: hex(value) for name, value in values.items()},
    }


def source_step(session: SessionState, max_instructions: int = 100) -> dict:
    if not session.elf.is_loaded:
        return step_instruction(session)

    core = session.probe.read_core_registers()
    pc = core["pc"]
    initial = session.elf.addr_to_source(pc)
    if initial["file"] is None or initial["line"] is None:
        return step_instruction(session)

    cur_file = initial["file"]
    cur_line = initial["line"]
    for instruction_count in range(1, max_instructions + 1):
        result = session.probe.step()
        new_pc_hex = result.get("pc")
        if not new_pc_hex:
            break

        new_pc = int(new_pc_hex, 16)
        new_src = session.elf.addr_to_source(new_pc)
        if new_src["file"] is not None and (
            new_src["file"] != cur_file or new_src["line"] != cur_line
        ):
            sym = session.elf.resolve_address(new_pc)
            source_str = f"{new_src['file']}:{new_src['line']}"
            return {
                "status": "ok",
                "summary": f"Stepped to {source_str}.",
                "pc": hex(new_pc),
                "instructions_executed": instruction_count,
                "source": source_str,
                "file": new_src["file"],
                "line": new_src["line"],
                "symbol": sym["symbol"],
            }

    core = session.probe.read_core_registers()
    final_pc = core["pc"]
    final_src = session.elf.addr_to_source(final_pc)
    final_resolved = session.elf.resolve_address(final_pc)
    return {
        "status": "ok",
        "summary": f"Executed up to {max_instructions} instruction(s) without crossing a source line boundary.",
        "pc": hex(final_pc),
        "instructions_executed": max_instructions,
        "source": final_resolved["source"],
        "file": final_src["file"],
        "line": final_src["line"],
        "symbol": final_resolved["symbol"],
    }


def disassemble(session: SessionState, address: int, count: int = 10) -> dict:
    try:
        from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
    except ImportError:
        return {"status": "error", "summary": "capstone is not installed."}
    size = count * 4
    try:
        data = session.probe.read_memory(address & ~1, size)
    except Exception as e:
        return {"status": "error", "summary": str(e)}
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
    instructions = []
    for insn in md.disasm(data, address & ~1):
        entry: dict = {
            "address": hex(insn.address),
            "bytes": insn.bytes.hex(),
            "mnemonic": insn.mnemonic,
            "op_str": insn.op_str,
            "text": f"{insn.mnemonic} {insn.op_str}".strip(),
        }
        if session.elf.is_loaded:
            src = session.elf.addr_to_source(insn.address)
            entry["source"] = f"{src['file']}:{src['line']}" if src["file"] else None
        instructions.append(entry)
        if len(instructions) >= count:
            break
    return {
        "status": "ok",
        "summary": f"Disassembled {len(instructions)} instruction(s) at {hex(address)}.",
        "address": hex(address),
        "instructions": instructions,
    }


def step_out(session: SessionState, timeout_seconds: float = 5.0) -> dict:
    core = session.probe.read_core_registers()
    pc = core["pc"] & ~1

    # Try DWARF CFI first — more reliable than LR under optimization
    ret_addr: int | None = None
    ret_source = "lr"
    if session.elf.is_loaded:
        cfi = session.elf.get_cfi_at(pc)
        if cfi is not None:
            cfa_reg = cfi.get("cfa_reg")
            cfa_offset = cfi.get("cfa_offset", 0)
            ra_offset = cfi.get("ra_offset")
            if cfa_reg is not None and ra_offset is not None:
                try:
                    cfa = core.get(cfa_reg, 0) + cfa_offset
                    saved_ra = int.from_bytes(
                        session.probe.read_memory(cfa + ra_offset, 4), "little"
                    )
                    if saved_ra > 0x100:
                        ret_addr = saved_ra & ~1
                        ret_source = "dwarf_cfi"
                except Exception:
                    pass

    if ret_addr is None:
        ret_addr = core["lr"] & ~1

    with temporary_breakpoint(session.probe, ret_addr):
        result = session.probe.continue_target(
            timeout_seconds=timeout_seconds, poll_interval_seconds=0.05
        )

    new_pc = int(result.get("pc", hex(ret_addr)), 16)
    src = (
        session.elf.addr_to_source(new_pc)
        if session.elf.is_loaded
        else {"file": None, "line": None}
    )
    sym = session.elf.resolve_address(new_pc)["symbol"] if session.elf.is_loaded else None
    return {
        "status": "ok",
        "summary": f"Stepped out to {hex(new_pc)}.",
        "pc": hex(new_pc),
        "return_address": hex(ret_addr),
        "return_address_source": ret_source,
        "source": f"{src['file']}:{src['line']}" if src["file"] else None,
        "symbol": sym,
    }


def step_over(session: SessionState, max_source_instructions: int = 100) -> dict:
    try:
        from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
    except ImportError:
        return source_step(session, max_instructions=max_source_instructions)
    core = session.probe.read_core_registers()
    pc = core["pc"] & ~1
    try:
        data = session.probe.read_memory(pc, 4)
    except Exception as e:
        return {"status": "error", "summary": str(e)}
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
    insns = list(md.disasm(data, pc))
    if not insns:
        return step_instruction(session)
    insn = insns[0]
    if insn.mnemonic.lower() in ("bl", "blx"):
        return_addr = insn.address + insn.size
        with temporary_breakpoint(session.probe, return_addr):
            result = session.probe.continue_target(timeout_seconds=5.0, poll_interval_seconds=0.05)
        new_pc = int(result.get("pc", hex(return_addr)), 16)
        src = (
            session.elf.addr_to_source(new_pc)
            if session.elf.is_loaded
            else {"file": None, "line": None}
        )
        sym = session.elf.resolve_address(new_pc)["symbol"] if session.elf.is_loaded else None
        return {
            "status": "ok",
            "summary": f"Stepped over '{insn.mnemonic} {insn.op_str}'.",
            "pc": hex(new_pc),
            "stepped_over": f"{insn.mnemonic} {insn.op_str}".strip(),
            "source": f"{src['file']}:{src['line']}" if src["file"] else None,
            "symbol": sym,
        }
    return source_step(session, max_instructions=max_source_instructions)
