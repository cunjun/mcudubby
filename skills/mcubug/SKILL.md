---
name: mcubug
description: Use when debugging embedded MCU boards or firmware with McuBuddy, pyOCD, J-Link, ST-Link, CMSIS-DAP, HardFault/crash symptoms, boot failures, silent UART/SPI/I2C/GPIO peripherals, CPU register or memory inspection, ELF/DWARF source debugging, SVD peripheral registers, FreeRTOS task state, RTT/UART logs, Keil UV4 build/flash loops, GDB servers, or board bring-up.
---

# mcubug

## Core Principle

Use `McuBuddy` as a structured evidence collector for real embedded boards. Prefer direct hardware
evidence over speculation, non-destructive reads before writes, and symptom-oriented diagnosis
before manual low-level probing.

McuBuddy v0.5.2 defaults to the `core` profile. Start with evidence collectors and only recommend
`MCUBUDDY_TOOL_PROFILE=full` when the required capability is hidden from the current MCP session.

## Reference Selection

Load only the reference needed for the current task:

| Situation | Read |
| --- | --- |
| First setup | `references/quickstart.md` |
| Windows MCP client configuration | `references/windows-mcp-config-example.md` |
| Unknown target, CMSIS-Pack, Keil project discovery, smoke test | `references/generic-board-workflow.md` |
| Need exact tool names or grouped command index | `references/tool-reference.md` |
| Need backend capability, target metadata, or known limits | `references/support-matrix.md` |
| AI is driving a debug session | `references/ai-playbook.md` |
| Need compact examples for a common symptom | `references/ai-examples.md` |
| Firmware command reaches an actuator but hardware does not move | `references/peripheral-actuator-debug-playbook.md` |
| Recording or updating real-board validation evidence | `references/board-validation-guide.md` |

If direct `McuBuddy` MCP tools are not available, explain that missing integration and provide the
exact tool sequence or setup change the user should run.

## Default Flow

When the user reports a board problem and has not specified commands:

1. Resolve ambiguous target names with `match_chip_name(...)` or `get_target_info(...)`.
2. Configure the probe with `configure_probe(...)`.
3. Connect with `probe_connect(...)`.
4. Establish a known stop point with `probe_halt()` or `probe_reset(halt=True)`.
5. Collect broad state with `read_stopped_context()` or the relevant evidence package.
6. Use `collect_crash_evidence(...)`, `collect_startup_evidence(...)`,
   `collect_peripheral_evidence(...)`, or `collect_rtos_evidence(...)` for symptom-specific facts.
7. Load `configure_elf(...)` / `elf_load(...)` when symbol or source evidence is available.
8. Load `svd_load(...)` when peripheral or clock state matters.
9. Inspect `read_rtt_log()`, `log_tail(...)`, `list_rtos_tasks()`, and `rtos_task_context(...)`
   when logs or RTOS state matter.

## Concurrency and Session Ordering

Treat one `McuBuddy` server session as one ordered hardware-debug channel. The server serializes
tools that share probe, backend, ELF/SVD, log, build, or runtime configuration state. Independent
server sessions may execute in parallel, and stateless metadata queries may overlap session work.

- Await each stateful hardware command before interpreting or reporting its result.
- Do not use parallel calls to reorder reset, halt, resume, memory access, backend configuration,
  build, flash, or disconnect steps; the server will serialize them in arrival order.
- Cancelling a request does not interrupt a synchronous probe SDK call already in progress. Wait
  for it to finish before assuming the probe or backend is available for another operation.
- Use separate server sessions for independent boards that must be operated in parallel.

## Symptom Routing

| Symptom | Start With |
| --- | --- |
| Board will not boot | `collect_startup_evidence(...)`, then crash evidence if fault state is present |
| HardFault or crash | `collect_crash_evidence(...)`, then `backtrace()` |
| UART/SPI/I2C/GPIO silent | `svd_load(...)`, `collect_peripheral_evidence(...)`, `svd_read_peripheral(...)` |
| Interrupt issue | Crash/peripheral evidence, NVIC state, handler symbols; `full` adds specialized diagnosis |
| Memory corruption | Crash evidence, stack checks, snapshots; `full` adds specialized diagnosis/watchpoints |
| Stack overflow | Crash/RTOS evidence and stack usage; `full` adds specialized diagnosis |
| FreeRTOS stall | `collect_rtos_evidence(...)`, then task context when a task is named |
| Clock issue | RCC/clock SVD evidence; `full` adds specialized diagnosis |
| Need path proof | Enable `full`, then use run-to-location or source stepping |
| Actuator command ACKed but no motion/output | Use the actuator playbook evidence ladder |

## Backend Guidance

- Use pyOCD for ST-Link or CMSIS-DAP unless the user gives a reason to prefer J-Link.
- Use J-Link for J-Link probes, native RTT, DWT cycle counter, or J-Link GDB server workflows.
- Prefer backend-canonical target names: lower-case pyOCD names such as `stm32f103c8`, and
  J-Link device names such as `STM32F103C8`.
- If attach is unstable, lower SWD speed, try attach-under-reset, check target power/wiring/reset,
  and look for stale GDB/J-Link/debugger processes.

## Safety Rules

Distinguish execution-changing actions (reset, halt, resume, stepping, breakpoints/watchpoints),
state-changing actions (register or memory writes), and persistent actions (flash erase/program and
build/flash loops).

Before persistent or destructive actions, confirm target, address range, firmware image, and user
intent unless the user already explicitly requested that action.

For flash loops:

1. collect evidence
2. build or patch firmware
3. `build_project(...)`
4. `flash_firmware(...)` or `erase_flash(...)` / `program_flash(...)`
5. `compare_elf_to_flash(...)`
6. reset/halt and collect fresh evidence

For motors, relays, power switches, and other actuators: prefer breakpoints and read-only
instrumentation first, use short/low-energy commands, and separate firmware path, bus transaction,
peripheral state, and power/output/load evidence.

## Reporting Template

When reporting findings, separate facts from interpretation:

```text
Evidence:
- ...

Interpretation:
- ...

Likely next checks:
- ...

Safety notes:
- ...
```
