from __future__ import annotations

from ...session import SessionState


def list_rtos_tasks(
    session: SessionState,
    max_priorities: int = 32,
    task_name_len: int = 16,
) -> dict:
    """List all FreeRTOS tasks by walking the kernel's ready/delayed/suspended lists.

    Assumes standard ARM Cortex-M FreeRTOS TCB layout (no MPU, no Trace, no Stats):
      offset 0x00: pxTopOfStack
      offset 0x04: xStateListItem (ListItem_t, 20 B)
      offset 0x18: xEventListItem (ListItem_t, 20 B)
      offset 0x2C: uxPriority
      offset 0x30: pxStack  (stack base, lowest address)
      offset 0x34: pcTaskName[task_name_len]
    Requires ELF loaded and probe connected.
    """
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded."}

    def _sym(name: str) -> int | None:
        r = session.elf.resolve_symbol(name)
        return int(r["address"], 16) if r["address"] is not None else None

    def read32(addr: int) -> int:
        return int.from_bytes(session.probe.read_memory(addr, 4), "little")

    # --- kernel globals ---
    current_tcb_ptr = _sym("pxCurrentTCB")
    if current_tcb_ptr is None:
        return {
            "status": "error",
            "summary": "Symbol 'pxCurrentTCB' not found — is this a FreeRTOS target?",
        }

    try:
        running_tcb = read32(current_tcb_ptr)
        num_tasks_ptr = _sym("uxCurrentNumberOfTasks")
        num_tasks = read32(num_tasks_ptr) if num_tasks_ptr else None
    except Exception as e:
        return {"status": "error", "summary": f"Failed to read FreeRTOS globals: {e}"}

    # --- list walker: List_t layout: uxNumberOfItems(4) pxIndex(4) xListEnd(12) ---
    # xListEnd is a MiniListItem_t: xItemValue(4) pxNext(4) pxPrev(4)
    # ListItem_t: xItemValue(4) pxNext(4) pxPrev(4) pvOwner(4) pxContainer(4)
    LIST_END_OFFSET = 8  # offset of xListEnd within List_t
    LIST_ITEM_NEXT_OFFSET = 4  # pxNext within ListItem_t
    LIST_ITEM_OWNER_OFFSET = 12  # pvOwner within ListItem_t

    def _walk_list(list_addr: int) -> list[int]:
        """Return TCB addresses from a FreeRTOS List_t."""
        owners: list[int] = []
        try:
            n_items = read32(list_addr)
            if n_items == 0 or n_items > 512:
                return owners
            end_addr = list_addr + LIST_END_OFFSET  # address of xListEnd
            cur = read32(end_addr + LIST_ITEM_NEXT_OFFSET)  # first real item
            for _ in range(min(n_items, 512)):
                if cur == 0 or cur == end_addr:
                    break
                owner = read32(cur + LIST_ITEM_OWNER_OFFSET)
                if owner and owner not in owners:
                    owners.append(owner)
                cur = read32(cur + LIST_ITEM_NEXT_OFFSET)
        except Exception:
            pass
        return owners

    # --- collect TCB addresses from all lists ---
    tcb_addrs: dict[int, str] = {}  # addr → state string

    # ready lists
    ready_list_ptr = _sym("pxReadyTasksLists")
    if ready_list_ptr is not None:
        LIST_T_SIZE = 20
        for pri in range(max_priorities):
            for addr in _walk_list(ready_list_ptr + pri * LIST_T_SIZE):
                tcb_addrs.setdefault(addr, "ready")

    # delayed lists
    for sym in (
        "xDelayedTaskList1",
        "xDelayedTaskList2",
        "pxDelayedTaskList",
        "pxOverflowDelayedTaskList",
    ):
        ptr = _sym(sym)
        if ptr is not None:
            target = read32(ptr) if sym.startswith("px") else ptr
            for addr in _walk_list(target):
                tcb_addrs.setdefault(addr, "blocked")

    # suspended list
    sus_ptr = _sym("xSuspendedTaskList")
    if sus_ptr is not None:
        for addr in _walk_list(sus_ptr):
            tcb_addrs.setdefault(addr, "suspended")

    # mark running task
    if running_tcb in tcb_addrs:
        tcb_addrs[running_tcb] = "running"
    elif running_tcb:
        tcb_addrs[running_tcb] = "running"

    # --- read each TCB ---
    TCB_TOP_OF_STACK = 0x00
    TCB_PRIORITY = 0x2C
    TCB_STACK_BASE = 0x30
    TCB_NAME = 0x34

    tasks: list[dict] = []
    for tcb_addr, state in tcb_addrs.items():
        try:
            top_of_stack = read32(tcb_addr + TCB_TOP_OF_STACK)
            priority = read32(tcb_addr + TCB_PRIORITY)
            stack_base = read32(tcb_addr + TCB_STACK_BASE)
            name_bytes = session.probe.read_memory(tcb_addr + TCB_NAME, task_name_len)
            name = name_bytes.split(b"\x00")[0].decode("utf-8", errors="replace")
        except Exception as e:
            tasks.append({"tcb_address": hex(tcb_addr), "state": state, "error": str(e)})
            continue

        stack_used: int | None = None
        if stack_base and top_of_stack >= stack_base:
            stack_used = top_of_stack - stack_base

        task: dict = {
            "name": name,
            "state": state,
            "priority": priority,
            "tcb_address": hex(tcb_addr),
            "top_of_stack": hex(top_of_stack),
            "stack_base": hex(stack_base),
            "stack_used_bytes": stack_used,
        }
        if session.elf.is_loaded:
            r = session.elf.resolve_address(top_of_stack)
            task["pc_symbol"] = r.get("symbol")
        tasks.append(task)

    tasks.sort(key=lambda t: (-t.get("priority", 0), t.get("name", "")))

    return {
        "status": "ok",
        "summary": f"Found {len(tasks)} FreeRTOS task(s). Current: '{tasks[0]['name'] if tasks else 'unknown'}'.",
        "task_count": len(tasks),
        "reported_task_count": num_tasks,
        "tasks": tasks,
    }
