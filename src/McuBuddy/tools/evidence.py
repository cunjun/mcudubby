from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..result import make_result, safety_info
from ..session import SessionState
from .probe.context import read_stopped_context
from .probe.rtos import list_rtos_tasks, rtos_task_context
from .svd import svd_read_peripheral


def _observe(kind: str, collector: Callable[[], Any]) -> dict[str, Any]:
    try:
        result = collector()
        status = "ok"
        if isinstance(result, dict) and result.get("status") == "error":
            status = "unavailable"
        return {"kind": kind, "status": status, "result": result}
    except Exception as exc:
        return {
            "kind": kind,
            "status": "unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _summarize(evidence: list[dict[str, Any]], topic: str) -> tuple[str, str]:
    ok = sum(1 for item in evidence if item["status"] == "ok")
    if ok == len(evidence):
        return "ok", f"Collected {topic} evidence from {ok} source(s)."
    if ok:
        return (
            "partial",
            f"Collected partial {topic} evidence from {ok}/{len(evidence)} source(s).",
        )
    return "error", f"No {topic} evidence could be collected; see unavailable observations."


def _recent_logs(session: SessionState, line_count: int) -> dict[str, Any]:
    lines = session.log.read_recent(line_count)
    return {
        "status": "ok",
        "line_count": len(lines),
        "last_lines": lines,
        "last_meaningful_line": next(
            (line for line in reversed(lines) if line.strip()), None
        ),
    }


def collect_crash_evidence(
    session: SessionState,
    *,
    auto_halt: bool = True,
    include_logs: bool = True,
    log_tail_lines: int = 50,
    resolve_symbols: bool = True,
    include_stack_snapshot: bool = True,
    stack_snapshot_bytes: int = 64,
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    if auto_halt:
        evidence.append(_observe("halt", session.probe.halt))

    evidence.append(
        _observe(
            "stopped_context",
            lambda: read_stopped_context(
                session,
                include_fault_registers=True,
                include_logs=include_logs,
                log_tail_lines=log_tail_lines,
                resolve_symbols=resolve_symbols,
            ),
        )
    )

    if include_stack_snapshot:
        def stack_snapshot() -> dict[str, Any]:
            core = session.probe.read_core_registers()
            sp = core["sp"]
            data = session.probe.read_memory(sp, stack_snapshot_bytes)
            return {
                "status": "ok",
                "start_address": hex(sp),
                "size_bytes": stack_snapshot_bytes,
                "data_hex": data.hex(" "),
            }

        evidence.append(_observe("stack_snapshot", stack_snapshot))

    status, summary = _summarize(evidence, "crash")
    return make_result(
        status=status,
        summary=summary,
        evidence=evidence,
        next_tools=["backtrace", "collect_rtos_evidence"],
        safety=safety_info(
            "execution-changing",
            "May halt the target when auto_halt is true.",
        ),
    )


def collect_startup_evidence(
    session: SessionState,
    *,
    reset_and_halt: bool = False,
    include_logs: bool = True,
    log_tail_lines: int = 50,
    resolve_symbols: bool = True,
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    if reset_and_halt:
        evidence.append(_observe("reset_halt", lambda: session.probe.reset(halt=True)))
    evidence.append(
        _observe(
            "stopped_context",
            lambda: read_stopped_context(
                session,
                include_fault_registers=True,
                include_logs=include_logs,
                log_tail_lines=log_tail_lines,
                resolve_symbols=resolve_symbols,
            ),
        )
    )
    evidence.append(
        _observe(
            "vector_words",
            lambda: session.probe.read_memory(0x00000000, 16).hex(" "),
        )
    )
    if include_logs:
        evidence.append(_observe("logs", lambda: _recent_logs(session, log_tail_lines)))

    status, summary = _summarize(evidence, "startup")
    return make_result(
        status=status,
        summary=summary,
        evidence=evidence,
        next_tools=["collect_crash_evidence", "svd_read_peripheral"],
        safety=safety_info(
            "execution-changing",
            "Only resets the target when reset_and_halt is true.",
        ),
    )


def collect_peripheral_evidence(
    session: SessionState,
    *,
    peripheral: str,
    include_rcc: bool = True,
    include_gpio: bool = True,
) -> dict[str, Any]:
    evidence = [
        _observe(
            f"peripheral:{peripheral}",
            lambda: svd_read_peripheral(session, peripheral),
        )
    ]
    if include_rcc:
        evidence.append(
            _observe("peripheral:RCC", lambda: svd_read_peripheral(session, "RCC"))
        )
    if include_gpio:
        evidence.append(
            _observe("peripheral:GPIOA", lambda: svd_read_peripheral(session, "GPIOA"))
        )
        evidence.append(
            _observe("peripheral:GPIOB", lambda: svd_read_peripheral(session, "GPIOB"))
        )

    status, summary = _summarize(evidence, "peripheral")
    return make_result(
        status=status,
        summary=summary,
        evidence=evidence,
        next_tools=["svd_get_registers", "collect_startup_evidence"],
        safety=safety_info("read-only", "Reads SVD-backed peripheral registers only."),
        payload={"peripheral": peripheral},
    )


def collect_rtos_evidence(
    session: SessionState,
    *,
    task_name: str | None = None,
    max_priorities: int = 32,
    task_name_len: int = 16,
) -> dict[str, Any]:
    evidence = [
        _observe(
            "rtos_tasks",
            lambda: list_rtos_tasks(
                session,
                max_priorities=max_priorities,
                task_name_len=task_name_len,
            ),
        )
    ]
    if task_name:
        evidence.append(
            _observe(
                f"rtos_task_context:{task_name}",
                lambda: rtos_task_context(
                    session,
                    task_name=task_name,
                    task_name_len=task_name_len,
                ),
            )
        )

    status, summary = _summarize(evidence, "RTOS")
    return make_result(
        status=status,
        summary=summary,
        evidence=evidence,
        next_tools=["rtos_task_context", "read_stack_usage"],
        safety=safety_info(
            "read-only",
            "Reads RTOS symbols, task state, and task stack context.",
        ),
        payload={"task_name": task_name},
    )
