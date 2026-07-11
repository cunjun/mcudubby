from __future__ import annotations

from ...session import SessionState


_FREERTOS_LIST_T_SIZE = 20
_FREERTOS_LIST_END_OFFSET = 8
_FREERTOS_LIST_ITEM_NEXT_OFFSET = 4
_FREERTOS_LIST_ITEM_OWNER_OFFSET = 12
_TCB_TOP_OF_STACK = 0x00
_TCB_PRIORITY = 0x2C
_TCB_STACK_BASE = 0x30
_TCB_NAME = 0x34


def _resolve_symbol_addr(session: SessionState, name: str) -> int | None:
    resolved = session.elf.resolve_symbol(name)
    return int(resolved["address"], 16) if resolved["address"] is not None else None


def _read_u32(session: SessionState, address: int) -> int:
    return int.from_bytes(session.probe.read_memory(address, 4), "little")


def _walk_freertos_list(session: SessionState, list_addr: int) -> list[int]:
    owners: list[int] = []
    try:
        n_items = _read_u32(session, list_addr)
        if n_items == 0 or n_items > 512:
            return owners
        end_addr = list_addr + _FREERTOS_LIST_END_OFFSET
        cur = _read_u32(session, end_addr + _FREERTOS_LIST_ITEM_NEXT_OFFSET)
        for _ in range(min(n_items, 512)):
            if cur == 0 or cur == end_addr:
                break
            owner = _read_u32(session, cur + _FREERTOS_LIST_ITEM_OWNER_OFFSET)
            if owner and owner not in owners:
                owners.append(owner)
            cur = _read_u32(session, cur + _FREERTOS_LIST_ITEM_NEXT_OFFSET)
    except Exception:
        pass
    return owners


def _collect_freertos_tcb_states(
    session: SessionState,
    max_priorities: int = 32,
) -> tuple[dict[int, str], int | None]:
    current_tcb_ptr = _resolve_symbol_addr(session, "pxCurrentTCB")
    if current_tcb_ptr is None:
        raise LookupError("Symbol 'pxCurrentTCB' not found — is this a FreeRTOS target?")

    running_tcb = _read_u32(session, current_tcb_ptr)
    tcb_addrs: dict[int, str] = {}

    ready_list_ptr = _resolve_symbol_addr(session, "pxReadyTasksLists")
    if ready_list_ptr is not None:
        for pri in range(max_priorities):
            list_addr = ready_list_ptr + pri * _FREERTOS_LIST_T_SIZE
            for addr in _walk_freertos_list(session, list_addr):
                tcb_addrs.setdefault(addr, "ready")

    for sym in (
        "xDelayedTaskList1",
        "xDelayedTaskList2",
        "pxDelayedTaskList",
        "pxOverflowDelayedTaskList",
    ):
        ptr = _resolve_symbol_addr(session, sym)
        if ptr is None:
            continue
        try:
            target = _read_u32(session, ptr) if sym.startswith("px") else ptr
        except Exception:
            continue
        for addr in _walk_freertos_list(session, target):
            tcb_addrs.setdefault(addr, "blocked")

    sus_ptr = _resolve_symbol_addr(session, "xSuspendedTaskList")
    if sus_ptr is not None:
        for addr in _walk_freertos_list(session, sus_ptr):
            tcb_addrs.setdefault(addr, "suspended")

    if running_tcb:
        tcb_addrs[running_tcb] = "running"

    return tcb_addrs, running_tcb


def _read_freertos_task_name(session: SessionState, tcb_addr: int, task_name_len: int) -> str:
    name_bytes = session.probe.read_memory(tcb_addr + _TCB_NAME, task_name_len)
    return name_bytes.split(b"\x00")[0].decode("utf-8", errors="replace")
