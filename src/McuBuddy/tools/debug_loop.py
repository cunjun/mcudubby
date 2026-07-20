from __future__ import annotations

from ..session import SessionState
from .build import build_project, flash_firmware
from .configuration import connect_with_config, load_demo_profile
from .diagnose import diagnose_hardfault, diagnose_startup_failure
from .lifecycle import disconnect_all
from .logs import tail_logs
from .probe import clear_all_breakpoints
from .probe import continue_target
from .probe import read_stopped_context
from .probe import reset_target
from .probe import set_breakpoint


def run_debug_loop(
    session: SessionState,
    issue_description: str,
    profile_name: str | None = None,
    build_before_debug: bool = False,
    flash_before_debug: bool = False,
    confirm_flash_before_debug: bool = False,
    log_tail_lines: int = 30,
    suspected_stage: str | None = None,
) -> dict:
    actions: list[dict] = []

    if profile_name:
        actions.append(
            {"step": "load_demo_profile", "result": load_demo_profile(session, profile_name)}
        )

    symptom = _classify_issue_description(issue_description)
    actions.append({"step": "disconnect_all_preflight", "result": disconnect_all(session)})

    if build_before_debug:
        build_result = build_project(session)
        actions.append({"step": "build_project", "result": build_result})
        if build_result["status"] != "ok":
            return _debug_loop_result(
                status="error",
                issue_description=issue_description,
                symptom=symptom,
                summary="Debug loop stopped because firmware build failed.",
                actions=actions,
                final_diagnosis=build_result,
            )

    if flash_before_debug:
        flash_result = flash_firmware(session, confirm=confirm_flash_before_debug)
        actions.append({"step": "flash_firmware", "result": flash_result})
        if flash_result["status"] != "ok":
            return _debug_loop_result(
                status="error",
                issue_description=issue_description,
                symptom=symptom,
                summary="Debug loop stopped because firmware flash failed.",
                actions=actions,
                final_diagnosis=flash_result,
            )

    connect_result = connect_with_config(session)
    actions.append({"step": "connect_with_config", "result": connect_result})
    if connect_result["status"] not in {"ok", "partial"} or connect_result.get("errors"):
        return _debug_loop_result(
            status="error",
            issue_description=issue_description,
            symptom=symptom,
            summary="Debug loop stopped because hardware connection did not succeed cleanly.",
            actions=actions,
            final_diagnosis=connect_result,
        )

    if symptom == "led_not_blinking":
        breakpoint_result = _run_path_validation(
            session,
            symbol="sensor_init",
            log_tail_lines=log_tail_lines,
        )
        actions.extend(breakpoint_result["actions"])

    reset_result = reset_target(session, halt=False)
    actions.append({"step": "probe_reset", "result": reset_result})

    logs_result = tail_logs(session, line_count=log_tail_lines)
    actions.append({"step": "log_tail", "result": logs_result})

    startup_result = diagnose_startup_failure(
        session,
        suspected_stage=suspected_stage or _infer_suspected_stage(symptom, issue_description),
        include_logs=True,
        log_tail_lines=log_tail_lines,
        resolve_symbols=True,
    )
    actions.append({"step": "diagnose_startup_failure", "result": startup_result})

    final_diagnosis = startup_result
    if startup_result.get("fault", {}).get("fault_detected"):
        hardfault_result = diagnose_hardfault(
            session,
            suspected_stage=suspected_stage or _infer_suspected_stage(symptom, issue_description),
            include_logs=True,
            log_tail_lines=log_tail_lines,
            resolve_symbols=True,
            include_fault_registers=True,
            include_stack_snapshot=True,
            stack_snapshot_bytes=32,
        )
        actions.append({"step": "diagnose_hardfault", "result": hardfault_result})
        final_diagnosis = hardfault_result

    cleanup_result = disconnect_all(session)
    actions.append({"step": "disconnect_all_cleanup", "result": cleanup_result})

    summary = _summarize_final_result(symptom, final_diagnosis, startup_result, issue_description)
    return _debug_loop_result(
        status="ok",
        issue_description=issue_description,
        symptom=symptom,
        summary=summary,
        actions=actions,
        final_diagnosis=final_diagnosis,
    )


def _classify_issue_description(issue_description: str) -> str:
    normalized = issue_description.lower()
    if "\u706f" in issue_description or "led" in normalized:
        return "led_not_blinking"
    if "\u6ca1\u65e5\u5fd7" in issue_description or "no log" in normalized:
        return "no_boot_log"
    if "hardfault" in normalized:
        return "hardfault"
    if "\u4e0d\u542f\u52a8" in issue_description or "boot" in normalized:
        return "startup_failure"
    return "generic_board_issue"


def _infer_suspected_stage(symptom: str, issue_description: str) -> str | None:
    if symptom == "led_not_blinking":
        return "sensor init"
    if symptom == "no_boot_log":
        return "early boot"
    if symptom in {"hardfault", "startup_failure"}:
        return "sensor init"
    normalized = issue_description.lower()
    if "sensor" in normalized:
        return "sensor init"
    return None


def _summarize_final_result(
    symptom: str,
    final_diagnosis: dict,
    startup_result: dict,
    issue_description: str,
) -> str:
    diagnosis_type = startup_result.get("diagnosis_type")
    if diagnosis_type == "startup_completed_normally":
        return f"Debug loop for '{issue_description}' ended with a healthy startup result."
    if final_diagnosis.get("diagnosis_type") == "hardfault_detected":
        return (
            f"Debug loop for '{issue_description}' found a hard fault on the board "
            f"while investigating {symptom}."
        )
    if diagnosis_type == "startup_failure_with_fault":
        return f"Debug loop for '{issue_description}' found a startup-stage fault."
    return f"Debug loop for '{issue_description}' completed with a partial diagnosis."


def _run_path_validation(
    session: SessionState,
    symbol: str,
    log_tail_lines: int,
) -> dict:
    actions: list[dict] = []

    set_result = set_breakpoint(session, symbol=symbol, confirm=True)
    actions.append({"step": "set_breakpoint", "result": set_result})

    reset_halt_result = reset_target(session, halt=True)
    actions.append({"step": "probe_reset_halt_for_breakpoint", "result": reset_halt_result})

    continue_result = continue_target(
        session,
        timeout_seconds=3.0,
        poll_interval_ms=50,
    )
    actions.append({"step": "continue_target", "result": continue_result})

    context_result = read_stopped_context(
        session,
        include_fault_registers=True,
        include_logs=True,
        log_tail_lines=log_tail_lines,
        resolve_symbols=True,
    )
    actions.append({"step": "read_stopped_context", "result": context_result})

    clear_result = clear_all_breakpoints(session, confirm=True)
    actions.append({"step": "clear_all_breakpoints", "result": clear_result})

    return {"actions": actions}


def _debug_loop_result(
    status: str,
    issue_description: str,
    symptom: str,
    summary: str,
    actions: list[dict],
    final_diagnosis: dict,
) -> dict:
    return {
        "status": status,
        "issue_description": issue_description,
        "symptom_class": symptom,
        "summary": summary,
        "actions": actions,
        "final_diagnosis": final_diagnosis,
    }
