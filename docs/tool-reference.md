# Tool Reference

This page is the canonical grouped index for the public `McuBuddy` MCP tools. Keep short
workflow examples in [Quickstart](quickstart.md), scenario guidance in [AI Playbook](ai-playbook.md),
and capability status in [Support Matrix](support-matrix.md).

## Tool Profiles

McuBuddy v0.5.2 exposes the `core` profile by default. Set `MCUBUDDY_TOOL_PROFILE=full` at server
startup to expose the complete expert catalog. The active profile is fixed for the lifetime of the
MCP server process.

Core tools:

- `doctor`
- `first_contact`
- `list_tool_safety`
- `list_validation_records`
- `pack_diagnose`
- `pack_install`
- `match_chip_name`
- `get_target_info`
- `list_connected_probes`
- `configure_probe`
- `configure_elf`
- `elf_load`
- `svd_load`
- `probe_connect`
- `disconnect_all`
- `probe_halt`
- `probe_resume`
- `probe_reset`
- `read_stopped_context`
- `backtrace`
- `collect_crash_evidence`
- `collect_startup_evidence`
- `collect_peripheral_evidence`
- `collect_rtos_evidence`
- `svd_read_peripheral`
- `list_rtos_tasks`
- `rtos_task_context`
- `read_rtt_log`
- `configure_log`
- `log_connect`
- `uart_send`
- `uart_read_bytes`
- `uart_exchange`
- `log_tail`
- `discover_keil_projects`
- `configure_keil_project`
- `build_project`
- `flash_firmware`
- `flash_image`
- `compare_elf_to_flash`

`list_tool_safety()` lists only tools visible in the active profile. Use
`list_tool_safety(include_hidden=true)` to inspect metadata for the full catalog without changing
the MCP exposure surface.

Start a new session with `doctor()` and `first_contact()` before configuring a probe. The first
checks runtime/config readiness; the second summarizes session prerequisites and missing evidence.

`pack_diagnose(target, search_roots=None)` finds and checksum-verifies a managed CMSIS-Pack.
`pack_install(target, destination="packs", confirm=False)` downloads the exact trusted pack,
enforces a bounded size and checksum, then atomically installs it after `confirm=True`.

## Evidence Packages

- `collect_crash_evidence`
- `collect_startup_evidence`
- `collect_peripheral_evidence`
- `collect_rtos_evidence`

These tools return structured observations and missing prerequisites. They do not claim a root cause
unless that fact is directly present in collected evidence.

## Configuration And Bring-Up

Board bring-up helpers:

- `discover_keil_projects`
- `configure_keil_project`
- `board_smoke_test`

Runtime configuration and target preflight:

- `doctor`
- `first_contact`
- `get_runtime_config`
- `list_demo_profiles`
- `load_demo_profile`
- `configure_probe`
- `configure_log`
- `configure_elf`
- `configure_build`
- `connect_with_config`
- `match_chip_name`
- `get_target_info`
- `list_supported_targets`
- `list_tool_safety`
- `list_validation_records`

## Probe Control And Stepping

- `list_connected_probes`
- `probe_connect`
- `probe_disconnect`
- `probe_halt`
- `probe_resume`
- `probe_reset`
- `probe_step`
- `continue_target`
- `probe_continue_until`
- `step_over`
- `step_out`
- `source_step`
- `run_to_source`
- `run_to_function`

## Breakpoints And Watchpoints

- `set_breakpoint`
- `set_breakpoints_for_function_range`
- `clear_breakpoint`
- `clear_all_breakpoints`
- `probe_set_watchpoint`
- `probe_remove_watchpoint`
- `probe_clear_all_watchpoints`

## Registers, Memory, Flash, And State

- `probe_read_registers`
- `probe_read_fpu_registers`
- `probe_read_mpu_regions`
- `probe_read_memory`
- `probe_write_memory`
- `dump_memory`
- `memory_find`
- `memory_snapshot`
- `memory_diff`
- `read_memory_map`
- `read_stopped_context`
- `erase_flash`
- `program_flash`
- `flash_image`
- `verify_flash`
- `read_cycle_counter`
- `read_swo_log`

`program_flash(address, data, verify=True, confirm=False)` is a low-level write operation. It
does not erase Flash first; only use it when the destination range is already erased.

`flash_image(path, address, erase_mode="sector", verify=True, reset_after=True, confirm=False)`
reads a raw binary from an allowed host path, erases the affected sectors (or the whole chip with
`erase_mode="chip"`), programs it, verifies it, and optionally resets the target. Both Flash erase
and programming must be enabled, and this persistent operation requires `confirm=True`.

## ELF And DWARF

- `elf_load`
- `elf_addr_to_source`
- `elf_list_functions`
- `elf_symbol_info`
- `read_symbol_value`
- `write_symbol_value`
- `watch_symbol`
- `disassemble`
- `backtrace`
- `dwarf_backtrace`
- `get_locals`
- `set_local`
- `log_trace`
- `reset_and_trace`
- `compare_elf_to_flash`

## Logs, RTOS, And RTT

- `log_connect`
- `log_disconnect`
- `uart_send`
- `uart_read_bytes`
- `uart_exchange`
- `log_tail`
- `list_rtos_tasks`
- `rtos_task_context`
- `read_rtt_log`
- `read_stack_usage`

`uart_send(data, data_format, confirm=False)` writes bytes to the UART channel opened by
`log_connect`. Use `data_format="hex"` for compact or whitespace-separated hexadecimal bytes,
or `data_format="text"` for UTF-8 text. Because a UART command can change target behavior, the
tool requires `confirm=True`.

`uart_read_bytes(timeout_ms=1000, max_bytes=4096, idle_timeout_ms=50)` reads raw UART bytes
without line splitting or text decoding. It returns hexadecimal data, byte count, first/last-byte
timing, and overall/idle timeout flags. This is a read-only tool.

`uart_exchange(data, data_format, timeout_ms=1000, max_bytes=4096,
idle_timeout_ms=50, confirm=False)` writes a request and collects the raw binary response until
the byte limit, overall timeout, or post-response idle timeout is reached. It returns both TX and
RX evidence and requires `confirm=True` because it sends data to the target.

## SVD And Peripheral Diagnosis

- `svd_load`
- `svd_list_peripherals`
- `svd_get_registers`
- `svd_read_peripheral`
- `svd_write_register`
- `svd_write_field`
- `diagnose_peripheral_stuck`

## Higher-Level Diagnosis

- `diagnose`
- `diagnose_hardfault`
- `diagnose_startup_failure`
- `diagnose_memory_corruption`
- `diagnose_stack_overflow`
- `diagnose_interrupt_issue`
- `diagnose_clock_issue`
- `run_debug_loop`

## Build, Flash, GDB, And Lifecycle

- `build_project`
- `flash_firmware`
- `start_gdb_server`
- `stop_gdb_server`
- `get_gdb_server_status`
- `start_jlink_gdb_server`
- `stop_jlink_gdb_server`
- `get_jlink_gdb_server_status`
- `disconnect_all`

`start_gdb_server` binds to localhost by default. Remote binding requires both
`allow_remote=True` and `confirm_remote=True` because the GDB server has no authentication.
