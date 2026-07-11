from __future__ import annotations

from typing import Any


SAFETY_LEVELS: dict[str, dict[str, Any]] = {
    "read-only": {
        "summary": "Reads configuration, debug state, symbols, logs, or metadata.",
        "requires_confirmation": False,
    },
    "execution-changing": {
        "summary": "Changes target execution state, such as halt, resume, reset, or continue.",
        "requires_confirmation": False,
    },
    "state-changing": {
        "summary": "Writes target runtime state, such as memory, registers, breakpoints, or watchpoints.",
        "requires_confirmation": True,
    },
    "persistent-destructive": {
        "summary": "Changes persistent target state, especially flash erase/program or firmware flashing.",
        "requires_confirmation": True,
    },
    "host-process": {
        "summary": "Starts, stops, or inspects host-side helper processes.",
        "requires_confirmation": False,
    },
}


TOOL_SAFETY: dict[str, dict[str, Any]] = {
    "doctor": {"level": "read-only"},
    "first_contact": {"level": "read-only"},
    "board_smoke_test": {"level": "read-only"},
    "get_runtime_config": {"level": "read-only"},
    "list_connected_probes": {"level": "read-only"},
    "list_supported_targets": {"level": "read-only"},
    "match_chip_name": {"level": "read-only"},
    "get_target_info": {"level": "read-only"},
    "read_stopped_context": {"level": "read-only"},
    "probe_read_registers": {"level": "read-only"},
    "probe_read_memory": {"level": "read-only"},
    "dump_memory": {"level": "read-only"},
    "read_rtt_log": {"level": "read-only"},
    "log_tail": {"level": "read-only"},
    "svd_read_peripheral": {"level": "read-only"},
    "diagnose": {"level": "read-only"},
    "diagnose_hardfault": {"level": "read-only"},
    "diagnose_startup_failure": {"level": "read-only"},
    "diagnose_peripheral_stuck": {"level": "read-only"},
    "diagnose_memory_corruption": {"level": "read-only"},
    "diagnose_interrupt_issue": {"level": "read-only"},
    "diagnose_clock_issue": {"level": "read-only"},
    "diagnose_stack_overflow": {"level": "read-only"},
    "probe_halt": {"level": "execution-changing"},
    "probe_resume": {"level": "execution-changing"},
    "probe_reset": {"level": "execution-changing"},
    "continue_target": {"level": "execution-changing"},
    "probe_step": {"level": "execution-changing"},
    "source_step": {"level": "execution-changing"},
    "step_over": {"level": "execution-changing"},
    "step_out": {"level": "execution-changing"},
    "run_to_function": {"level": "execution-changing"},
    "run_to_source": {"level": "execution-changing"},
    "set_breakpoint": {"level": "state-changing"},
    "clear_breakpoint": {"level": "state-changing"},
    "clear_all_breakpoints": {"level": "state-changing"},
    "probe_set_watchpoint": {"level": "state-changing"},
    "probe_remove_watchpoint": {"level": "state-changing"},
    "probe_clear_all_watchpoints": {"level": "state-changing"},
    "probe_read_mpu_regions": {"level": "state-changing"},
    "probe_write_memory": {"level": "state-changing"},
    "write_symbol_value": {"level": "state-changing"},
    "set_local": {"level": "state-changing"},
    "svd_write_register": {"level": "state-changing"},
    "svd_write_field": {"level": "state-changing"},
    "erase_flash": {"level": "persistent-destructive"},
    "program_flash": {"level": "persistent-destructive"},
    "flash_firmware": {"level": "persistent-destructive"},
    "build_project": {"level": "host-process"},
    "start_gdb_server": {"level": "host-process"},
    "stop_gdb_server": {"level": "host-process"},
    "get_gdb_server_status": {"level": "host-process"},
    "start_jlink_gdb_server": {"level": "host-process"},
    "stop_jlink_gdb_server": {"level": "host-process"},
    "get_jlink_gdb_server_status": {"level": "host-process"},
}


def get_tool_safety(tool_name: str) -> dict[str, Any]:
    entry = dict(TOOL_SAFETY.get(tool_name, {"level": "unknown"}))
    level_info = SAFETY_LEVELS.get(
        entry["level"],
        {"summary": "No safety metadata is registered.", "requires_confirmation": True},
    )
    entry.update(level_info)
    return entry


def require_tool_confirmation(tool_name: str, confirmed: bool) -> dict[str, Any] | None:
    safety = get_tool_safety(tool_name)
    if confirmed or not safety["requires_confirmation"]:
        return None
    summary = (
        f"{tool_name} is a {safety['level']} operation and requires explicit confirmation."
    )
    return {
        "status": "error",
        "summary": summary,
        "safety": safety,
        "next_tools": ["list_tool_safety"],
    }

def list_tool_safety() -> dict[str, Any]:
    return {
        "status": "ok",
        "summary": f"Listed safety metadata for {len(TOOL_SAFETY)} tool(s).",
        "safety_levels": SAFETY_LEVELS,
        "tools": {name: get_tool_safety(name) for name in sorted(TOOL_SAFETY)},
    }
