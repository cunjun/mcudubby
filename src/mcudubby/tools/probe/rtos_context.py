from __future__ import annotations

from ...session import SessionState
from ...tool_safety import require_tool_confirmation
from .rtos_helpers import (
    _collect_freertos_tcb_states,
    _read_freertos_task_name,
    _read_u32,
    _TCB_TOP_OF_STACK,
)


def rtos_task_context(
    session: SessionState,
    task_name: str,
    task_name_len: int = 16,
    max_priorities: int = 32,
) -> dict:
    """Read saved register context of a blocked/suspended FreeRTOS task.

    Parses the Cortex-M4F context switch stack frame from pxTopOfStack.
    Software frame (STMDB {R4-R11, LR}): R4-R11 at +0..+28, EXC_RETURN at +32.
    If FPU was active (EXC_RETURN bit 4 = 0), S16-S31 precede the software frame (+64 offset).
    Hardware frame follows: R0-R3, R12, LR, PC, xPSR.
    If the named task is currently running, returns live registers instead.
    Requires ELF loaded and probe connected.
    """
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded."}
    try:
        tcb_addrs, current_tcb = _collect_freertos_tcb_states(
            session, max_priorities=max_priorities
        )
    except LookupError as exc:
        return {"status": "error", "summary": str(exc)}
    except Exception as exc:
        return {"status": "error", "summary": f"Failed to enumerate FreeRTOS tasks: {exc}"}

    # --- find TCB matching task_name ---
    target_tcb: int | None = None
    for tcb_addr in tcb_addrs:
        try:
            name = _read_freertos_task_name(session, tcb_addr, task_name_len)
            if name == task_name:
                target_tcb = tcb_addr
                break
        except Exception:
            continue

    if target_tcb is None:
        return {
            "status": "error",
            "summary": f"Task '{task_name}' not found in FreeRTOS task lists.",
        }

    # --- running task: return live registers ---
    if target_tcb == current_tcb:
        try:
            core = session.probe.read_core_registers()
            regs = {k: hex(v) for k, v in core.items()}
            resolved = session.elf.resolve_address(core["pc"] & ~1)
            return {
                "status": "ok",
                "summary": f"Task '{task_name}' is currently running; live registers returned.",
                "task_name": task_name,
                "tcb_address": hex(target_tcb),
                "state": "running",
                "fpu_context": False,
                "registers": regs,
                "pc_symbol": resolved.get("symbol"),
                "source": resolved.get("source"),
            }
        except Exception as e:
            return {"status": "error", "summary": str(e)}

    # --- blocked/suspended task: parse saved Cortex-M4F context frame ---
    # ARM_CM4F port layout (STMDB {R4-R11, LR} then hardware frame):
    #   no-FPU (EXC_RETURN bit4=1): SW frame at +0, EXC_RETURN at +32, HW frame at +36
    #   FPU    (EXC_RETURN bit4=0): S16-S31 at +0..+63, SW frame at +64, EXC_RETURN at +96, HW frame at +100
    try:
        tos = _read_u32(session, target_tcb + _TCB_TOP_OF_STACK)  # pxTopOfStack is first TCB field

        # Detect FPU by checking EXC_RETURN at both possible positions
        exc_nofpu = _read_u32(session, tos + 32)
        exc_fpu = _read_u32(session, tos + 96)
        is_exc = lambda v: (v & 0xFFFFFF00) == 0xFFFFFF00  # noqa: E731

        if is_exc(exc_nofpu):
            sw_base = tos
            exc_return = exc_nofpu
            fpu_active = (exc_return & 0x10) == 0
        elif is_exc(exc_fpu):
            sw_base = tos + 64  # S16-S31 precede the SW frame
            exc_return = exc_fpu
            fpu_active = True
        else:
            sw_base = tos  # fallback: assume no FPU
            exc_return = exc_nofpu
            fpu_active = False

        hw_base = sw_base + 36  # 9 words: R4-R11 (8) + EXC_RETURN (1)

        r4 = _read_u32(session, sw_base + 0)
        r5 = _read_u32(session, sw_base + 4)
        r6 = _read_u32(session, sw_base + 8)
        r7 = _read_u32(session, sw_base + 12)
        r8 = _read_u32(session, sw_base + 16)
        r9 = _read_u32(session, sw_base + 20)
        r10 = _read_u32(session, sw_base + 24)
        r11 = _read_u32(session, sw_base + 28)

        r0 = _read_u32(session, hw_base + 0)
        r1 = _read_u32(session, hw_base + 4)
        r2 = _read_u32(session, hw_base + 8)
        r3 = _read_u32(session, hw_base + 12)
        r12 = _read_u32(session, hw_base + 16)
        lr = _read_u32(session, hw_base + 20)
        pc = _read_u32(session, hw_base + 24) & ~1
        xpsr = _read_u32(session, hw_base + 28)

        # SP as it was at context switch (after popping full hw frame)
        # Extended hw frame (FPU): 8 std + S0-S15(16) + FPSCR(1) + pad(1) = 26 words = 104 B
        sp = hw_base + (104 if fpu_active else 32)

    except Exception as e:
        return {"status": "error", "summary": f"Failed to parse context frame: {e}"}

    resolved = session.elf.resolve_address(pc)
    return {
        "status": "ok",
        "summary": f"Parsed saved context for task '{task_name}': PC={hex(pc)} ({resolved.get('symbol') or 'unknown'}).",
        "task_name": task_name,
        "tcb_address": hex(target_tcb),
        "state": "blocked_or_suspended",
        "fpu_context": fpu_active,
        "exc_return": hex(exc_return),
        "registers": {
            "r0": hex(r0),
            "r1": hex(r1),
            "r2": hex(r2),
            "r3": hex(r3),
            "r4": hex(r4),
            "r5": hex(r5),
            "r6": hex(r6),
            "r7": hex(r7),
            "r8": hex(r8),
            "r9": hex(r9),
            "r10": hex(r10),
            "r11": hex(r11),
            "r12": hex(r12),
            "sp": hex(sp),
            "lr": hex(lr),
            "pc": hex(pc),
            "xpsr": hex(xpsr),
        },
        "pc_symbol": resolved.get("symbol"),
        "source": resolved.get("source"),
    }


def rtos_switch_context(
    session: SessionState,
    task_name: str,
    task_name_len: int = 16,
    confirm: bool = False,
) -> dict:
    """Switch CPU context to a blocked/suspended FreeRTOS task.

    After switching, you can single-step or continue to run the task from its saved context.
    Uses the saved exception frame from the task's stack stored in TCB.pxTopOfStack.
    """
    if blocked := require_tool_confirmation("rtos_switch_context", confirm):
        return blocked
    return {
        "status": "error",
        "summary": (
            "RTOS context switching is unavailable until the active probe backend provides "
            "validated core register writes; target memory was not modified."
        ),
        "task_name": task_name,
    }
