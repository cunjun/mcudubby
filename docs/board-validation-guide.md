# Board Validation Guide

This document is a practical checklist for validating `mcudubby` features on a real board.

Use it after:

- adding a new backend capability
- modifying demo firmware
- changing ELF / DWARF / RTOS / RTT logic
- bringing up a new probe or board target

The goal is to collect concrete evidence, not just confirm that a command did not crash.

## 1. Validation Principles

Prefer this order:

1. confirm the probe and target can attach
2. confirm one non-destructive read path with `board_smoke_test(...)`
3. confirm symbol/source resolution works
4. confirm the feature under test
5. record exact evidence in `PROGRESS.md`

Always prefer:

- real addresses
- real symbols
- real source lines
- real task names
- real log text

Avoid vague statements such as:

- "seems to work"
- "probably okay"
- "looks fine"

## 2. Minimum Validation Record

For any board-facing change, record:

- board name
- MCU
- probe type
- backend
- firmware image or demo used
- exact tool calls
- exact observed results
- any remaining limitation

Good examples:

- `run_to_function('main') -> pc=0x8008804, source=main.c:73`
- `rtos_task_context('Tmr Svc') -> prvProcessTimerOrBlockTask`
- `read_rtt_log() captured 'TimerCallback fired count=3'`

## 3. Recommended Validation Sequence

### A. Attach and stop-state sanity check

1. `list_connected_probes()`
2. `get_target_info(...)`
3. `configure_probe(...)`
4. `board_smoke_test(disconnect_after=True)`
5. `probe_connect(...)`
6. `probe_halt()` or `probe_reset(halt=True)`
7. `read_stopped_context()`

Expected evidence:

- target attached
- PC is readable
- state is readable
- symbol/source resolution works when ELF is loaded

### B. Symbol and source validation

1. `elf_load(...)`
2. `run_to_function(...)`
3. `source_step()`
4. `step_over()`
5. `step_out()`

Expected evidence:

- function name resolves
- source line changes are meaningful
- step operations return usable `pc`, `symbol`, and `source`

### C. RTT / log validation

1. `read_rtt_log()`
2. if needed, run backend-specific smoke scripts
3. verify actual text, not only control-block discovery

Expected evidence:

- non-empty text when firmware is expected to emit logs
- control block address if the implementation reports it
- known startup or heartbeat lines

### D. RTOS validation

1. `list_rtos_tasks()`
2. `rtos_task_context(...)`
3. `read_stack_usage()`

Expected evidence:

- task names are readable
- blocked tasks resolve to meaningful wait functions
- stack usage data is plausible

### E. Flash validation

1. `erase_flash(...)`
2. `program_flash(...)`
3. `verify_flash(...)`

Expected evidence:

- exact flash address range
- exact byte count
- explicit verify success

## 4. Probe-Specific Notes

### pyOCD

Use for:

- ST-Link
- CMSIS-DAP
- primary STM32L496 validation path
- CMSIS-Pack-supplied targets via `configure_probe(pack_path=...)`

Preferred evidence:

- source-level stepping
- SVD reads
- RTOS task inspection

### J-Link

Use for:

- native RTT
- J-Link GDB server
- DWT cycle counter

Be explicit about whether:

- the DLL path was auto-discovered
- serial selection worked directly or needed fallback
- SWO was only path-validated or fully text-validated

## 5. What Counts As Partial?

Mark a validation result as partial when:

- the feature path is callable but the firmware did not emit useful data
- the feature works in tests but not yet on real hardware
- the feature works on one board but not yet on the target board you care about
- the backend path works but the physical board wiring blocks the final signal

Examples:

- SWO host buffer reads succeed but no text is captured because the trace pin is not usable on that board
- RTT control block is found but no lines have been emitted yet

## 6. What To Update After Validation

After every meaningful validation round:

1. update `PROGRESS.md`
2. update `README.md` if public capability claims changed
3. update `README_CN.md` if the public Chinese summary changed
4. update `docs/support-matrix.md` if implementation or validation scope changed

## 7. Suggested Validation Snapshots

For a new backend feature:

- one focused unit-test run
- one real-board validation run
- one clear summary paragraph in `PROGRESS.md`

For a demo firmware extension:

- build result
- flash result
- one runtime log or task-context proof point

For a new diagnosis flow:

- one routed example
- one returned evidence set
- one recommended-next-tools sequence
