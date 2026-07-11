from __future__ import annotations

import operator as _op

from ...session import SessionState

_OPS = {
    "eq": _op.eq,
    "ne": _op.ne,
    "lt": _op.lt,
    "gt": _op.gt,
    "le": _op.le,
    "ge": _op.ge,
}


def _evaluate_condition(session: SessionState, cond: dict) -> bool:
    op_fn = _OPS.get(cond["condition_op"], _op.eq)
    expected = cond["condition_value"]

    if cond.get("condition_symbol"):
        if not session.elf.is_loaded:
            return True  # Can't evaluate — don't skip
        resolved = session.elf.resolve_symbol(cond["condition_symbol"])
        if resolved.get("address") is None:
            return True
        raw = session.probe.read_memory(int(resolved["address"], 16), 4)
        observed = int.from_bytes(raw, "little")
    elif cond.get("condition_register"):
        registers = session.probe.read_core_registers()
        reg = cond["condition_register"]
        if reg not in registers:
            return True  # Unknown register — don't skip
        observed = int(registers[reg])
    else:
        return True  # No condition spec — always halt

    return op_fn(observed, expected)
