from __future__ import annotations

import bisect
import struct
from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

# ARM register index → name (for DWARF DW_OP_reg / DW_OP_breg)
_ARM_REGS = [
    "r0",
    "r1",
    "r2",
    "r3",
    "r4",
    "r5",
    "r6",
    "r7",
    "r8",
    "r9",
    "r10",
    "r11",
    "r12",
    "sp",
    "lr",
    "pc",
]


def _decode_sleb128(data: bytes | list[int]) -> int:
    result = 0
    shift = 0
    for byte in data:
        result |= (byte & 0x7F) << shift
        shift += 7
        if not (byte & 0x80):
            if byte & 0x40:
                result |= -(1 << shift)
            break
    return result


def _decode_uleb128(data: bytes | list[int]) -> int:
    result = 0
    shift = 0
    for byte in data:
        result |= (byte & 0x7F) << shift
        shift += 7
        if not (byte & 0x80):
            break
    return result


def _decode_name(val: Any) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


class ElfManager:
    def __init__(self) -> None:
        self._path: Path | None = None
        self._func_symbols: list[dict[str, Any]] = []
        self._all_symbols: list[dict[str, Any]] = []
        self._line_addrs: list[int] = []
        self._line_entries: list[tuple[str, int]] = []
        self._func_locals: list[dict[str, Any]] = []
        self._cfi_entries: list[dict[str, Any]] = []
        self._cfi_pcs: list[int] = []

    def load(self, path: str) -> dict[str, Any]:
        file_path = Path(path)
        with file_path.open("rb") as handle:
            elf = ELFFile(handle)
            self._func_symbols, self._all_symbols = self._load_symbols(elf)
            self._line_addrs, self._line_entries = self._build_line_table(elf)
            self._func_locals = self._build_func_locals(elf)
            self._cfi_entries, self._cfi_pcs = self._build_cfi_index(elf)
        self._path = file_path
        return {
            "status": "ok",
            "summary": f"Loaded ELF symbols from {file_path.name}.",
            "symbol_count": len(self._func_symbols),
            "line_entry_count": len(self._line_addrs),
            "func_with_locals": len(self._func_locals),
            "cfi_entries": len(self._cfi_entries),
        }

    def addr_to_source(self, address: int) -> dict[str, Any]:
        if not self._line_addrs:
            return {"file": None, "line": None}
        idx = bisect.bisect_right(self._line_addrs, address) - 1
        if idx < 0:
            return {"file": None, "line": None}
        filename, line = self._line_entries[idx]
        return {"file": filename, "line": line}

    def resolve_address(self, address: int) -> dict[str, Any]:
        best_match = None
        for symbol in self._func_symbols:
            start = symbol["address"]
            end = start + max(symbol["size"], 1)
            if start <= address < end:
                best_match = symbol
                break
        source_info = self.addr_to_source(address)
        filename = source_info["file"]
        line = source_info["line"]
        return {
            "address": hex(address),
            "symbol": None if best_match is None else best_match["name"],
            "source": f"{filename}:{line}" if filename is not None and line is not None else None,
        }

    def source_to_addrs(self, filename: str, line: int) -> list[int]:
        matches = []
        for addr, (file, ln) in zip(self._line_addrs, self._line_entries):
            if ln != line:
                continue
            if file == filename or file.endswith("/" + filename) or file.endswith("\\" + filename):
                matches.append(addr)
        return matches

    def resolve_symbol(self, name: str) -> dict[str, Any]:
        match = next((s for s in self._all_symbols if s["name"] == name), None)
        return {
            "symbol": name,
            "address": None if match is None else hex(match["address"]),
            "size": None if match is None else match["size"],
            "source": None,
        }

    def get_locals_at(self, pc: int) -> list[dict[str, Any]]:
        """Return variable descriptors for the function containing pc."""
        addr = pc & ~1
        for func in self._func_locals:
            if func["low_pc"] <= addr < func["high_pc"]:
                return func["variables"]
        return []

    @property
    def is_loaded(self) -> bool:
        return self._path is not None

    def list_functions(self, name_filter: str | None = None) -> list[dict[str, Any]]:
        """Return function symbols, optionally filtered by substring match on name."""
        funcs = self._func_symbols
        if name_filter:
            low = name_filter.lower()
            funcs = [f for f in funcs if low in f["name"].lower()]
        return [{"name": f["name"], "address": hex(f["address"]), "size": f["size"]} for f in funcs]

    def symbol_info(self, name: str) -> dict[str, Any]:
        """Return address, size, type, source location for a symbol."""
        match = next((s for s in self._all_symbols if s["name"] == name), None)
        if match is None:
            return {"found": False, "name": name}
        src = self.addr_to_source(match["address"])
        return {
            "found": True,
            "name": name,
            "address": hex(match["address"]),
            "size": match["size"],
            "type": match.get("type", "unknown"),
            "source": f"{src['file']}:{src['line']}" if src["file"] else None,
        }

    def get_section_data(self) -> list[dict[str, Any]]:
        """Return allocated PROGBITS sections with content and load addresses."""
        if not self.is_loaded:
            return []
        sections = []
        with self._path.open("rb") as handle:
            elf = ELFFile(handle)
            load_segments = [
                segment for segment in elf.iter_segments() if segment["p_type"] == "PT_LOAD"
            ]
            for section in elf.iter_sections():
                if section["sh_type"] != "SHT_PROGBITS":
                    continue
                if not (section["sh_flags"] & 0x2):  # SHF_ALLOC
                    continue
                if section["sh_addr"] == 0 or section["sh_size"] == 0:
                    continue
                vma = int(section["sh_addr"])
                lma = None
                for segment in load_segments:
                    seg_vma = int(segment["p_vaddr"])
                    seg_memsz = int(segment["p_memsz"])
                    if seg_vma <= vma < seg_vma + max(seg_memsz, 1):
                        lma = int(segment["p_paddr"]) + (vma - seg_vma)
                        break
                sections.append(
                    {
                        "name": section.name,
                        "vma": vma,
                        "lma": lma,
                        "size": section["sh_size"],
                        "data": section.data(),
                    }
                )
        return sections

    def get_sections(self) -> list[dict[str, Any]]:
        """Return VMA, LMA, and size for each ELF section."""
        if not self.is_loaded:
            return []
        sections = []
        with self._path.open("rb") as handle:
            elf = ELFFile(handle)
            load_segments = [
                segment for segment in elf.iter_segments() if segment["p_type"] == "PT_LOAD"
            ]
            for section in elf.iter_sections():
                if section["sh_size"] == 0:
                    continue
                vma = int(section["sh_addr"])
                lma = None
                for segment in load_segments:
                    seg_vma = int(segment["p_vaddr"])
                    seg_memsz = int(segment["p_memsz"])
                    if seg_vma <= vma < seg_vma + max(seg_memsz, 1):
                        lma = int(segment["p_paddr"]) + (vma - seg_vma)
                        break
                sections.append(
                    {
                        "name": section.name,
                        "vma": hex(vma),
                        "lma": None if lma is None else hex(lma),
                        "size": section["sh_size"],
                    }
                )
        return sections

    # ------------------------------------------------------------------ #
    # Symbol table
    # ------------------------------------------------------------------ #

    def _load_symbols(self, elf: ELFFile) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        func_symbols: list[dict[str, Any]] = []
        all_symbols: list[dict[str, Any]] = []
        for section in elf.iter_sections():
            if not isinstance(section, SymbolTableSection):
                continue
            for symbol in section.iter_symbols():
                if not symbol.name:
                    continue
                symbol_type = symbol["st_info"]["type"]
                symbol_info = {
                    "name": symbol.name,
                    "address": int(symbol["st_value"]),
                    "size": int(symbol["st_size"]),
                    "type": symbol_type,
                }
                all_symbols.append(symbol_info)
                if symbol_type != "STT_FUNC":
                    continue
                func_symbols.append({**symbol_info, "address": symbol_info["address"] & ~1})
        return (
            sorted(func_symbols, key=lambda item: item["address"]),
            sorted(all_symbols, key=lambda item: item["address"]),
        )

    # ------------------------------------------------------------------ #
    # .debug_line
    # ------------------------------------------------------------------ #

    def _build_line_table(self, elf: ELFFile) -> tuple[list[int], list[tuple[str, int]]]:
        if not elf.has_dwarf_info():
            return [], []
        dwarf = elf.get_dwarf_info()
        rows: list[tuple[int, str, int]] = []
        for cu in dwarf.iter_CUs():
            try:
                lineprog = dwarf.line_program_for_CU(cu)
                if lineprog is None:
                    continue
                file_entries = lineprog["file_entry"]
                for entry in lineprog.get_entries():
                    state = entry.state
                    if state is None or state.end_sequence or state.line is None:
                        continue
                    if state.file < 1 or state.file > len(file_entries):
                        continue
                    raw_name = file_entries[state.file - 1].name
                    filename = _decode_name(raw_name)
                    rows.append((int(state.address), filename, int(state.line)))
            except Exception:
                continue
        rows.sort(key=lambda row: row[0])
        return [row[0] for row in rows], [(row[1], row[2]) for row in rows]

    # ------------------------------------------------------------------ #
    # .debug_info — Phase 5
    # ------------------------------------------------------------------ #

    def _build_func_locals(self, elf: ELFFile) -> list[dict[str, Any]]:
        if not elf.has_dwarf_info():
            return []
        dwarf = elf.get_dwarf_info()
        functions: list[dict[str, Any]] = []
        for cu in dwarf.iter_CUs():
            try:
                cu_offset = cu.cu_offset
                # Build die_map: abs_offset -> DIE (within this CU)
                die_map: dict[int, Any] = {}
                for die in cu.iter_DIEs():
                    die_map[die.offset] = die
                # Second pass: extract subprograms
                for die in cu.iter_DIEs():
                    if die.tag != "DW_TAG_subprogram":
                        continue
                    func = self._parse_subprogram(die, die_map, cu_offset)
                    if func:
                        functions.append(func)
            except Exception:
                continue
        return functions

    def _parse_subprogram(
        self, die: Any, die_map: dict[int, Any], cu_offset: int
    ) -> dict[str, Any] | None:
        low_attr = die.attributes.get("DW_AT_low_pc")
        high_attr = die.attributes.get("DW_AT_high_pc")
        if low_attr is None or high_attr is None:
            return None
        low_pc = int(low_attr.value) & ~1
        # high_pc is offset if it's a data form, absolute if addr form
        if high_attr.form in (
            "DW_FORM_data1",
            "DW_FORM_data2",
            "DW_FORM_data4",
            "DW_FORM_data8",
            "DW_FORM_udata",
            "DW_FORM_sdata",
        ):
            high_pc = low_pc + int(high_attr.value)
        else:
            high_pc = int(high_attr.value) & ~1

        frame_base_reg = self._parse_frame_base(die)
        variables: list[dict[str, Any]] = []
        for child in die.iter_children():
            if child.tag not in ("DW_TAG_variable", "DW_TAG_formal_parameter"):
                continue
            var = self._parse_var_die(child, die_map, cu_offset)
            if var:
                variables.append(var)
        return {
            "low_pc": low_pc,
            "high_pc": high_pc,
            "frame_base_reg": frame_base_reg,
            "variables": variables,
        }

    def _parse_frame_base(self, die: Any) -> str:
        fb = die.attributes.get("DW_AT_frame_base")
        if fb is None:
            return "sp"
        if fb.form == "DW_FORM_exprloc":
            expr = fb.value
            if expr:
                op = expr[0]
                if 0x50 <= op <= 0x5F:  # DW_OP_reg0..15
                    idx = op - 0x50
                    return _ARM_REGS[idx] if idx < len(_ARM_REGS) else "sp"
                if 0x70 <= op <= 0x7F:  # DW_OP_breg0..15
                    idx = op - 0x70
                    return _ARM_REGS[idx] if idx < len(_ARM_REGS) else "sp"
        return "sp"

    def _parse_var_die(
        self, die: Any, die_map: dict[int, Any], cu_offset: int
    ) -> dict[str, Any] | None:
        name_attr = die.attributes.get("DW_AT_name")
        if name_attr is None:
            return None
        name = _decode_name(name_attr.value)
        loc = self._parse_location(die)
        type_info = self._resolve_type(die, die_map, cu_offset, depth=0)
        return {
            "name": name,
            "type_name": type_info["name"],
            "byte_size": type_info["byte_size"],
            "loc_type": loc["type"],
            "loc_value": loc["value"],
        }

    def _parse_location(self, die: Any) -> dict[str, Any]:
        loc_attr = die.attributes.get("DW_AT_location")
        if loc_attr is None:
            return {"type": "unknown", "value": None}
        if loc_attr.form != "DW_FORM_exprloc":
            # Location list reference — skip for now
            return {"type": "unknown", "value": None}
        expr = loc_attr.value
        if not expr:
            return {"type": "unknown", "value": None}
        op = expr[0]
        # DW_OP_addr (0x03) — absolute address
        if op == 0x03 and len(expr) >= 5:
            addr = struct.unpack_from("<I", bytes(expr[1:5]))[0]
            return {"type": "addr", "value": addr}
        # DW_OP_fbreg (0x77) — SLEB128 offset from frame base
        if op == 0x77 and len(expr) >= 2:
            offset = _decode_sleb128(expr[1:])
            return {"type": "fbreg", "value": offset}
        # DW_OP_reg0..15 (0x50..0x5F) — value is in register
        if 0x50 <= op <= 0x5F:
            idx = op - 0x50
            return {"type": "reg", "value": _ARM_REGS[idx] if idx < len(_ARM_REGS) else f"r{idx}"}
        # DW_OP_breg0..15 (0x70..0x7F) — SLEB128 offset from register
        if 0x70 <= op <= 0x7F and len(expr) >= 2:
            idx = op - 0x70
            reg = _ARM_REGS[idx] if idx < len(_ARM_REGS) else f"r{idx}"
            offset = _decode_sleb128(expr[1:])
            return {"type": "breg", "value": (reg, offset)}
        return {"type": "unknown", "value": None}

    def _resolve_type(
        self, die: Any, die_map: dict[int, Any], cu_offset: int, depth: int
    ) -> dict[str, Any]:
        if depth > 6:
            return {"name": "unknown", "byte_size": 4}
        type_attr = die.attributes.get("DW_AT_type")
        if type_attr is None:
            return {"name": "void", "byte_size": 0}
        # Resolve absolute offset
        form = type_attr.form
        if form in (
            "DW_FORM_ref1",
            "DW_FORM_ref2",
            "DW_FORM_ref4",
            "DW_FORM_ref8",
            "DW_FORM_ref_udata",
        ):
            abs_offset = cu_offset + int(type_attr.value)
        else:
            abs_offset = int(type_attr.value)
        type_die = die_map.get(abs_offset)
        if type_die is None:
            return {"name": "unknown", "byte_size": 4}
        return self._extract_type(type_die, die_map, cu_offset, depth + 1)

    def _extract_type(
        self, die: Any, die_map: dict[int, Any], cu_offset: int, depth: int
    ) -> dict[str, Any]:
        if depth > 6:
            return {"name": "unknown", "byte_size": 4}
        tag = die.tag

        def size() -> int:
            a = die.attributes.get("DW_AT_byte_size")
            return int(a.value) if a else 4

        def name_attr() -> str | None:
            a = die.attributes.get("DW_AT_name")
            return _decode_name(a.value) if a else None

        def follow() -> dict[str, Any]:
            return self._resolve_type(die, die_map, cu_offset, depth)

        if tag == "DW_TAG_base_type":
            return {"name": name_attr() or "unknown", "byte_size": size()}

        if tag == "DW_TAG_pointer_type":
            inner = follow()
            return {"name": f"{inner['name']}*", "byte_size": size()}

        if tag in (
            "DW_TAG_typedef",
            "DW_TAG_const_type",
            "DW_TAG_volatile_type",
            "DW_TAG_restrict_type",
        ):
            inner = follow()
            if tag == "DW_TAG_typedef":
                n = name_attr()
                if n:
                    return {"name": n, "byte_size": inner["byte_size"]}
            return inner

        if tag in ("DW_TAG_structure_type", "DW_TAG_union_type"):
            prefix = "struct" if tag == "DW_TAG_structure_type" else "union"
            n = name_attr()
            label = f"{prefix} {n}" if n else prefix
            return {"name": label, "byte_size": size()}

        if tag == "DW_TAG_enumeration_type":
            n = name_attr() or ""
            return {"name": f"enum {n}".strip(), "byte_size": size()}

        if tag == "DW_TAG_array_type":
            inner = follow()
            return {"name": f"{inner['name']}[]", "byte_size": size()}

        return {"name": tag.replace("DW_TAG_", ""), "byte_size": size()}

    # ------------------------------------------------------------------ #
    # .debug_frame — Phase 5
    # ------------------------------------------------------------------ #

    # ARM DWARF register index → core register name
    _DWARF_TO_CORE: dict[int, str] = {i: f"r{i}" for i in range(13)}
    _DWARF_TO_CORE[13] = "sp"
    _DWARF_TO_CORE[14] = "lr"
    _DWARF_TO_CORE[15] = "pc"

    def _build_cfi_index(self, elf: ELFFile) -> tuple[list[dict[str, Any]], list[int]]:
        """Parse .debug_frame and build a PC-sorted list of FDE records."""
        if not elf.has_dwarf_info():
            return [], []
        dwarf = elf.get_dwarf_info()
        try:
            has_cfi = dwarf.has_CFI()
        except Exception:
            return [], []
        if not has_cfi:
            return [], []

        try:
            from elftools.dwarf.callframe import FDE as _FDE
        except ImportError:
            return [], []

        entries: list[dict[str, Any]] = []
        try:
            cfi_entries = dwarf.CFI_entries()
        except Exception:
            return [], []

        for cfi_entry in cfi_entries:
            if not isinstance(cfi_entry, _FDE):
                continue
            try:
                pc_start = int(cfi_entry.header["initial_location"]) & ~1
                pc_end = pc_start + int(cfi_entry.header["address_range"])
                decoded = cfi_entry.get_decoded()
                row_pcs: list[int] = []
                rows: list[dict[str, Any]] = []
                for row in decoded.table:
                    rpc = int(row["pc"]) & ~1
                    cfa = row.get("cfa")
                    if cfa is None:
                        continue
                    cfa_reg = int(cfa.reg)
                    cfa_off = int(cfa.offset)
                    # Return address = DWARF column 14 (LR) on ARM
                    ra_rule = row.get(14)
                    ra_offset: int | None = None
                    if ra_rule is not None:
                        try:
                            if ra_rule.type.name == "OFFSET":
                                ra_offset = int(ra_rule.arg)
                        except Exception:
                            pass
                    row_pcs.append(rpc)
                    rows.append({"cfa_reg": cfa_reg, "cfa_offset": cfa_off, "ra_offset": ra_offset})
                if rows:
                    entries.append(
                        {"pc_start": pc_start, "pc_end": pc_end, "row_pcs": row_pcs, "rows": rows}
                    )
            except Exception:
                continue

        entries.sort(key=lambda e: e["pc_start"])
        pcs = [e["pc_start"] for e in entries]
        return entries, pcs

    def get_cfi_at(self, pc: int) -> dict[str, Any] | None:
        """Return the applicable CFI row for pc, or None if not found."""
        addr = pc & ~1
        # Binary search for FDE containing addr
        idx = bisect.bisect_right(self._cfi_pcs, addr) - 1
        if idx < 0:
            return None
        entry = self._cfi_entries[idx]
        if addr >= entry["pc_end"]:
            return None
        # Find applicable row within FDE
        row_idx = bisect.bisect_right(entry["row_pcs"], addr) - 1
        if row_idx < 0:
            return None
        return entry["rows"][row_idx]
