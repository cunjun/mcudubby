from __future__ import annotations

from ...session import SessionState

_DWARF_REG_TO_CORE: dict[int, str] = {i: f"r{i}" for i in range(13)}
_DWARF_REG_TO_CORE[13] = "sp"
_DWARF_REG_TO_CORE[14] = "lr"
_DWARF_REG_TO_CORE[15] = "pc"


def dwarf_backtrace(session: SessionState, max_frames: int = 16) -> dict:
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded. Load an ELF file first."}

    core = session.probe.read_core_registers()

    def read32(addr: int) -> int:
        return int.from_bytes(session.probe.read_memory(addr, 4), "little")

    def make_frame(idx: int, pc: int) -> dict:
        resolved = session.elf.resolve_address(pc)
        return {
            "frame": idx,
            "address": hex(pc),
            "symbol": resolved["symbol"],
            "source": resolved["source"],
        }

    frames: list[dict] = []
    cur_pc = core["pc"] & ~1
    cur_regs: dict = dict(core)

    for i in range(max_frames):
        frames.append(make_frame(i, cur_pc))
        cfi = session.elf.get_cfi_at(cur_pc)

        if cfi is None:
            # No CFI — leaf function or missing .debug_frame; use LR as return address
            lr_val = cur_regs.get("lr", 0) & ~1
            if lr_val >= 0x100 and lr_val != cur_pc and i + 1 < max_frames:
                frames.append(make_frame(i + 1, lr_val))
            break

        # Compute Canonical Frame Address
        cfa_reg_name = _DWARF_REG_TO_CORE.get(cfi["cfa_reg"], "sp")
        cfa = cur_regs.get(cfa_reg_name, 0) + cfi["cfa_offset"]

        # Recover return address
        ra_offset = cfi["ra_offset"]
        if ra_offset is None:
            # LR not saved — still in register (leaf-like epilogue)
            ret_addr = cur_regs.get("lr", 0) & ~1
        else:
            try:
                ret_addr = read32(cfa + ra_offset) & ~1
            except Exception:
                break

        if ret_addr < 0x100 or ret_addr == cur_pc:
            break

        cur_pc = ret_addr
        cur_regs = dict(cur_regs)
        cur_regs["sp"] = cfa

    return {
        "status": "ok",
        "summary": f"Found {len(frames)} frame(s) via DWARF .debug_frame.",
        "frame_count": len(frames),
        "frames": frames,
    }


def backtrace(
    session: SessionState,
    max_frames: int = 20,
    stack_scan_words: int = 64,
) -> dict:
    core = session.probe.read_core_registers()
    pc = core["pc"] & ~1
    lr = core["lr"]
    sp = core["sp"]

    def make_frame(addr: int, idx: int) -> dict:
        frame: dict = {"frame": idx, "address": hex(addr)}
        if session.elf.is_loaded:
            resolved = session.elf.resolve_address(addr)
            frame["symbol"] = resolved["symbol"]
            frame["source"] = resolved["source"]
        else:
            frame["symbol"] = None
            frame["source"] = None
        return frame

    def is_exc_return(val: int) -> bool:
        return (val & 0xFF000000) == 0xFF000000

    frames: list[dict] = []
    seen: set[int] = set()

    # Frame 0 — current PC
    frames.append(make_frame(pc, 0))
    seen.add(pc)

    # Frame 1 — LR (return address from current function)
    if not is_exc_return(lr) and lr > 0x100:
        lr_addr = lr & ~1
        if lr_addr not in seen:
            f = make_frame(lr_addr, 1)
            if not session.elf.is_loaded or f["symbol"] is not None:
                frames.append(f)
                seen.add(lr_addr)

    # Frame 2+ — scan stack for saved return addresses
    for i in range(0, stack_scan_words * 4, 4):
        if len(frames) >= max_frames:
            break
        try:
            word = int.from_bytes(session.probe.read_memory(sp + i, 4), "little")
        except Exception:
            break
        if is_exc_return(word) or word < 0x100:
            continue
        addr = word & ~1
        if addr in seen:
            continue
        if session.elf.is_loaded:
            resolved = session.elf.resolve_address(addr)
            if resolved["symbol"] is None:
                continue
        seen.add(addr)
        frames.append(make_frame(addr, len(frames)))

    return {
        "status": "ok",
        "summary": f"Found {len(frames)} frame(s).",
        "frame_count": len(frames),
        "frames": frames,
    }
