# AI Playbook

This document is a short operational guide for AI assistants using `McuBubby`.

Use it to decide:

- which tools to call first
- which preconditions must be satisfied
- how to combine probe, ELF, SVD, RTT, RTOS, and diagnosis flows
- when to stop collecting evidence and start reasoning

`McuBubby` is a structured evidence collector.  
The AI is responsible for interpretation, prioritization, and next-step decisions.

---

## 1. Core Principle

Default strategy:

1. connect to the board
2. collect broad evidence
3. narrow to the failing subsystem
4. only then perform targeted deep inspection

Prefer:

- non-destructive reads before writes
- direct evidence before speculation
- built-in diagnosis tools before manual low-level probing
- real hardware evidence over assumptions

---

## 2. Default Workflow

When the user reports a board problem and does not specify a tool sequence:

1. If the target name may be ambiguous, call `match_chip_name(...)` or `get_target_info(...)`
2. `configure_probe(...)`
3. `probe_connect(...)`
4. `probe_halt()` or `probe_reset(halt=True)`
5. `read_stopped_context()`
6. If the symptom is broad, call `diagnose(...)`
7. If symbols are available, call `elf_load(...)`
8. If peripheral state matters, call `svd_load(...)`
9. If RTOS or logs matter, inspect `read_rtt_log()` and `list_rtos_tasks()`

Use this as the default decision tree:

- boot failure: `diagnose("board won't boot")`
- crash/hardfault: `diagnose_hardfault()`
- silent peripheral: `diagnose_peripheral_stuck(...)`
- actuator does not move after a command: follow
  [Peripheral Actuator Debug Playbook](peripheral-actuator-debug-playbook.md)
- RTOS stall: `list_rtos_tasks()` -> `rtos_task_context(...)`
- suspicious code path: `run_to_function()` / `run_to_source()` / `source_step()`

---

## 3. Target Preflight

Before connecting to a board with a user-supplied chip name:

1. Call `list_supported_targets(backend)` if you want to see the built-in support matrix first.
2. Call `match_chip_name(target, backend)` if you only need canonicalization.
3. Call `get_target_info(target, backend)` if you also want board/chip guidance.
4. Then call `configure_probe(...)` with the resolved backend and target.
5. Then call `probe_connect(...)`.

Use `get_target_info(...)` when:

- the user gave a package/full marketing name like `STM32F103C8T6`
- the backend has different preferred target strings
- you want preflight warnings or recovery guidance before the first attach

Use `list_supported_targets(...)` when:

- the user did not provide a precise MCU string
- you want to know which target names are already validated
- you want to choose a backend based on proven board coverage

Interpretation:

- `support_tier`: whether this target/backend pair is `validated`, `known`, or `unknown`
- `validated_hardware`: board/probe combinations already exercised on real hardware
- `validated_capabilities`: the parts of the workflow already proven on that target/backend pair
- `matched_target`: backend-specific target string that should actually be used
- `connect_hints`: preferred speed/attach strategy for that board family
- `warnings`: likely board-specific pitfalls
- `recovery_guidance`: what to try next if attach is unstable
- `post_connect_checks`: lightweight sanity checks that may run automatically after connect

---

## 4. Preconditions Matrix

### Probe-only tools

Require:

- connected probe

Examples:

- `probe_halt`
- `probe_resume`
- `probe_reset`
- `probe_step`
- `dump_memory`
- `probe_read_registers`
- `erase_flash`
- `program_flash`
- `verify_flash`

### ELF/DWARF tools

Require:

- probe connected for live state
- `elf_load(...)` for symbol/source resolution

Examples:

- `elf_addr_to_source`
- `elf_list_functions`
- `elf_symbol_info`
- `disassemble`
- `backtrace`
- `dwarf_backtrace`
- `get_locals`
- `run_to_function`
- `run_to_source`
- `source_step`

### SVD/peripheral tools

Require:

- probe connected
- `svd_load(...)`

Examples:

- `svd_read_peripheral`
- `svd_write_register`
- `svd_write_field`
- `diagnose_peripheral_stuck`

### RTOS tools

Require:

- probe connected
- matching ELF
- FreeRTOS symbols present in the image

Examples:

- `list_rtos_tasks`
- `rtos_task_context`
- `read_stack_usage`

Validated demo patterns on the STM32L496 test board include:

- queue producer/consumer
- semaphore handoff
- software timer service task
- event group wait (`xEventGroupWaitBits`)
- task notify (`ulTaskNotifyTake`)
- mutex wait path
- ISR-to-task notify from a timer interrupt

### RTT tools

Require:

- probe connected
- target firmware compiled with RTT support

Notes:

- `pyOCD` path may use RAM-scan fallback
- `J-Link` path now supports native RTT reads and may still fall back when needed
- finding the RTT control block is not the same as having text available immediately

### GDB server tools

Require:

- matching backend/runtime available
- target name configured

Examples:

- `start_gdb_server`
- `start_jlink_gdb_server`

---

## 5. Backend Guidance

### pyOCD

Use when:

- board is attached through ST-Link or CMSIS-DAP
- you want the most mature default backend path

Strengths:

- broad coverage
- strong STM32 workflow
- good default path for ST-Link

Patch-aware guidance:

- prefers canonical lower-case target strings such as `stm32f103c8`
- may automatically retry with lower frequency or `under-reset`

### J-Link

Use when:

- board is attached through J-Link
- you need J-Link-specific flows such as native RTT or J-Link GDB server

Validated capabilities:

- connect / halt / reset / continue / step
- source-level debugging
- watchpoints
- flash erase / program / verify
- J-Link GDB server
- native RTT reads

Notes:

- DLL auto-discovery is supported
- some setups may reject explicit serial selection for `JLinkGDBServerCL`
- stale local processes can block new J-Link sessions; clean shutdown matters
- prefers canonical J-Link device names such as `STM32F103C8`
- may automatically retry lower SWD speeds before failing

---

## 6. Recommended Tool Groups

### Bring-up and execution control

Use first when the board is unresponsive or you need a known stop point.

Primary tools:

- `match_chip_name`
- `get_target_info`
- `configure_probe`
- `probe_connect`
- `probe_halt`
- `probe_reset`
- `continue_target`
- `probe_step`
- `step_over`
- `step_out`
- `source_step`

### Symbol and source inspection

Use when the CPU is halted and you need to know where execution is.

Primary tools:

- `read_stopped_context`
- `elf_addr_to_source`
- `elf_symbol_info`
- `run_to_function`
- `run_to_source`
- `disassemble`
- `get_locals`

### Memory and registers

Use when validating raw state or corruption.

Primary tools:

- `probe_read_registers`
- `probe_read_memory`
- `dump_memory`
- `memory_snapshot`
- `memory_diff`
- `read_symbol_value`
- `write_symbol_value`

### Peripheral diagnosis

Use when UART/SPI/I2C/GPIO/clocking seems wrong.

Primary tools:

- `svd_read_peripheral`
- `svd_write_field`
- `diagnose_peripheral_stuck`
- `diagnose_clock_issue`

### RTOS and logs

Use when the firmware is alive but behavior is wrong.

Primary tools:

- `read_rtt_log`
- `list_rtos_tasks`
- `rtos_task_context`
- `read_stack_usage`

### Flash and recovery

Use only after non-destructive inspection unless the user is clearly asking to reflash.

Primary tools:

- `erase_flash`
- `program_flash`
- `verify_flash`
- `compare_elf_to_flash`

---

## 7. Diagnosis Patterns

### Pattern: board won't boot

1. `get_target_info`
2. `configure_probe`
3. `probe_connect`
4. `probe_reset(halt=True)`
5. `read_stopped_context`
6. `diagnose("board won't boot")`
7. If PC is in startup or a fault handler, use `backtrace` / `disassemble`

### Pattern: hardfault after reset

1. `get_target_info`
2. `probe_connect`
3. `probe_halt`
4. `diagnose_hardfault`
5. `backtrace` or `dwarf_backtrace`
6. `get_locals`
7. inspect fault registers and nearby memory

### Pattern: UART has no output

1. `diagnose("UART has no output")`
2. `svd_read_peripheral("USARTx")`
3. inspect GPIO alternate function / RCC enable / baud settings
4. if firmware should log, inspect `read_rtt_log()` or UART logs

### Pattern: FreeRTOS task appears stuck

1. `list_rtos_tasks`
2. `rtos_task_context(task_name=...)`
3. `read_stack_usage`
4. inspect blocked primitive:
   - queue
   - semaphore
   - timer service

### Pattern: verify J-Link RTT

1. `get_target_info(target, backend="jlink")`
2. `configure_probe(backend="jlink", ...)`
3. `probe_connect(...)`
4. `read_rtt_log(channel=0)`
5. if text is empty but control block is visible, retry
6. if needed, use `scripts/jlink_rtt_smoke.py`

### Pattern: first attach to an unfamiliar board

1. `list_connected_probes`
2. `get_target_info`
3. inspect `warnings` and `recovery_guidance`
4. `configure_probe`
5. `probe_connect`
6. inspect `target_patch` and `post_connect`

---

## 8. Interpretation Rules

### Treat these as evidence, not conclusions

- `status`
- `summary`
- `evidence`
- register dumps
- fault bits
- peripheral fields
- RTOS state
- RTT text

### Common interpretation tips

- `status = error` often means missing preconditions, not necessarily a broken implementation
- `source` and `symbol` usually provide the fastest next debugging branch
- `bytes_available = 0` for RTT does not prove RTT is broken
- RTOS state labels should be interpreted together with PC/source context
- `condition_skip_count` on conditional breakpoints is useful evidence of retry behavior
- `target_patch` explains why the backend may have used a different speed or attach strategy
- `post_connect` is evidence that the target was responsive immediately after attach

---

## 9. Validated Hardware Paths

The most trustworthy current paths are:

- `STM32L496VETx + ST-Link (pyOCD)`
- `STM32F103C8 + J-Link`

Validated J-Link path includes:

- source-level debug
- flash operations
- GDB server
- RTT

---

## 10. Safe Operation Rules

Prefer this order:

1. read state
2. inspect symbols/source
3. inspect peripherals/logs/RTOS
4. only then write memory, change registers, or flash

Before using temporary validation scripts:

- prefer checked-in scripts under `scripts/`
- avoid ad-hoc `python -u -` pipelines
- ensure probe disconnect happens in `finally`

If a probe session behaves strangely:

- suspect stale local processes
- clean J-Link / GDB / Python helpers before retrying

---

## 11. Suggested Companion Material

This playbook works best together with:

- `README.md` for capability overview
- `PROGRESS.md` for current verified status
- scenario demos for board-specific debugging flows

When adding a new major capability:

1. update implementation
2. add tests
3. validate on real hardware when possible
4. update `PROGRESS.md`
5. update this playbook if the default AI workflow should change
