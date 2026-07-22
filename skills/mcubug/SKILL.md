---
name: mcubug
description: Use when debugging MCU firmware or boards with McuBuddy, including probe connection, boot or HardFault crashes, silent peripherals, register/memory/ELF/SVD inspection, RTOS or RTT/UART evidence, Keil build/flash, GDB, and board bring-up through pyOCD, J-Link, ST-Link, or CMSIS-DAP.
---

# mcubug

## Core Principle

Collect reproducible hardware evidence. Prefer reads over speculation, separate facts from
hypotheses, and repeat the same checks after changes. McuBuddy v0.5.2 starts in `core`; use `full`
only when core evidence proves it is needed.

## Reference Selection

Load only the reference needed for the current task:

| Situation | Read |
| --- | --- |
| First setup, runtime/config preflight | `references/quickstart.md` |
| Windows MCP client configuration | `references/windows-mcp-config-example.md` |
| Unknown target, CMSIS-Pack, Keil project discovery, smoke test | `references/generic-board-workflow.md` |
| Need exact tool names or grouped command index | `references/tool-reference.md` |
| Need backend capability, target metadata, or known limits | `references/support-matrix.md` |
| AI is driving a debug session | `references/ai-playbook.md` |
| Need compact examples for a common symptom | `references/ai-examples.md` |
| Firmware command reaches an actuator but hardware does not move | `references/peripheral-actuator-debug-playbook.md` |
| Recording or updating real-board validation evidence | `references/board-validation-guide.md` |

If tools are unavailable, state that integration is missing and give the required setup or sequence.

## Default Flow

For a board problem without requested commands:

1. Run `doctor()` and `first_contact()`; report missing runtime, profile, probe, target, ELF, or SVD prerequisites.
2. Resolve ambiguous targets with `match_chip_name(...)` or `get_target_info(...)`.
3. Use `configure_probe(...)`, then `probe_connect(...)`.
4. Establish a known state with `probe_halt()` or `probe_reset(halt=True)`.
5. Call `read_stopped_context()` and the matching `collect_*_evidence` tool.
6. Add `configure_elf(...)` / `elf_load(...)`, `svd_load(...)`, logs, or RTOS context only when useful.
7. Form a hypothesis, predict distinguishing evidence, perform the smallest safe check, then verify.

## Profile Boundary

- Keep the default path inside `core`.
- A full-only call requires `MCUBUDDY_TOOL_PROFILE=full` before startup and a restart; a running
  core session cannot expose it.
- Use `list_tool_safety(include_hidden=true)` to inspect hidden metadata without changing profiles.

## Symptom Routing

| Symptom | Start With |
| --- | --- |
| Board will not boot | `collect_startup_evidence(...)`, then crash evidence if fault state is present |
| HardFault or crash | `collect_crash_evidence(...)`, then `backtrace()` |
| UART/SPI/I2C/GPIO silent | `svd_load(...)`, `collect_peripheral_evidence(...)`, `svd_read_peripheral(...)` |
| Interrupt issue | Crash/peripheral evidence, NVIC state, handler symbols |
| Memory corruption | Crash evidence, repeatable snapshots, stack and symbol checks |
| Stack overflow | Crash/RTOS evidence and stack context |
| FreeRTOS stall | `collect_rtos_evidence(...)`, then task context when a task is named |
| Clock issue | RCC/clock SVD evidence |
| Need path proof | Full-only: restart in `full`, then use `run_to_function(...)` or `source_step()` |
| Actuator command ACKed but no motion/output | Use the actuator playbook evidence ladder |

## Ordering and Safety

- Treat one server session as one ordered hardware channel. Await stateful calls; use separate
  sessions for independent boards. Cancellation may not stop an in-progress probe SDK call.
- Classify calls as read-only, execution-changing, state-changing, or persistent. Confirm target,
  scope, firmware, intent, and recovery before writes or flash operations.
- For flash work: collect evidence, `build_project(...)`, `flash_firmware(...)`,
  `compare_elf_to_flash(...)`, reset/halt, and collect fresh evidence.
- RTT memory scanning is bounded by `security.max_rtt_scan_size` or
  `MCUBUDDY_MAX_RTT_SCAN_SIZE`; do not bypass that guard.
- For actuators, use short low-energy commands and separately prove firmware, bus, peripheral, and
  physical output/load behavior.

## Reporting Template

Report results in this order:

```text
Evidence:
- ...

Interpretation:
- ...

Missing/uncertain evidence:
- ...

Next safe check and impact:
- ...
```
