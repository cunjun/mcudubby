from __future__ import annotations

from ...session import SessionState
from .rtos_helpers import (
    _collect_freertos_tcb_states,
    _read_freertos_task_name,
    _read_u32,
    _TCB_STACK_BASE,
    _TCB_TOP_OF_STACK,
)


def read_stack_usage(
    session: SessionState,
    canary: int = 0xA5A5A5A5,
    task_name_len: int = 16,
    max_priorities: int = 32,
) -> dict:
    """Scan each FreeRTOS task's stack for the canary high-water mark.

    FreeRTOS initialises unused stack with tskSTACK_FILL_BYTE (0xa5).
    Scans from pxStack (base) upward to find the first non-canary word.
    Reports the minimum untouched stack bytes that remain from the low address.
    The standard Cortex-M TCB layout does not reliably expose the total stack size.
    """
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded."}

    try:
        tcb_addrs, _ = _collect_freertos_tcb_states(session, max_priorities=max_priorities)
    except LookupError as exc:
        return {"status": "error", "summary": str(exc)}
    except Exception as exc:
        return {"status": "error", "summary": f"Failed to enumerate FreeRTOS tasks: {exc}"}

    if not tcb_addrs:
        return {"status": "error", "summary": "No FreeRTOS tasks found. Is the scheduler running?"}

    canary_bytes = canary.to_bytes(4, "little")
    tasks: list[dict] = []
    for tcb in tcb_addrs:
        try:
            top_of_stack = _read_u32(session, tcb + _TCB_TOP_OF_STACK)
            stack_base = _read_u32(session, tcb + _TCB_STACK_BASE)
            name = _read_freertos_task_name(session, tcb, task_name_len)
        except Exception as e:
            tasks.append({"tcb_address": hex(tcb), "error": str(e)})
            continue

        min_free: int | None = None
        if stack_base:
            free_words = 0
            scan_started = False
            offset = 0
            while offset < 65536:
                try:
                    raw = session.probe.read_memory(stack_base + offset, 256)
                    scan_started = True
                except Exception:
                    break
                if not raw:
                    break
                stop = False
                for i in range(0, len(raw) - 3, 4):
                    if raw[i : i + 4] == canary_bytes:
                        free_words += 1
                        offset += 4
                    else:
                        stop = True
                        break
                if stop or len(raw) < 4:
                    break
            if scan_started:
                min_free = free_words * 4

        tasks.append(
            {
                "name": name,
                "tcb_address": hex(tcb),
                "stack_base": hex(stack_base),
                "top_of_stack": hex(top_of_stack),
                "min_free_bytes": min_free,
            }
        )

    tasks.sort(key=lambda t: t.get("name", ""))
    return {
        "status": "ok",
        "summary": f"Stack usage for {len(tasks)} task(s). Canary: {hex(canary)}.",
        "canary_value": hex(canary),
        "tasks": tasks,
    }
