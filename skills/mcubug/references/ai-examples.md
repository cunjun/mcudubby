# AI Examples

This document shows concrete `McuBuddy` workflows for common embedded-debug tasks.

The goal is not to list every tool. The goal is to show practical tool sequences, the important returned fields, and how an AI assistant should interpret the evidence.

## 1. Board Will Not Boot

User problem:

> This board does not boot after reset.

Recommended sequence:

1. `get_target_info(...)`
2. `configure_probe(...)`
3. `probe_connect(...)`
4. `probe_reset(halt=True)`
5. `read_stopped_context()`
6. `diagnose("board won't boot")`
7. If needed, `backtrace()` / `dwarf_backtrace()` / `disassemble(...)`

Most important fields:

- `pc`
- `symbol`
- `source`
- `stop_reason`
- `evidence`

Interpretation notes:

- If `pc` resolves to a fault handler, prefer `diagnose_hardfault()`.
- If the core stops in startup code, inspect clocks, vector table, and early init paths next.

## 2. HardFault After Reset

User problem:

> The firmware crashes into HardFault right after startup.

Recommended sequence:

1. `probe_connect(...)`
2. `probe_halt()`
3. `diagnose_hardfault()`
4. `dwarf_backtrace()`
5. `get_locals()`
6. `dump_memory(...)` or `read_symbol_value(...)` if memory corruption is suspected

Most important fields:

- `fault.registers`
- `symbol_context`
- `evidence`

Interpretation notes:

- Treat `evidence` as observations, not root-cause claims.
- Use `pc_symbol`, `source`, and fault bits together before concluding anything about the bug.

## 3. UART Has No Output

User problem:

> USART2 has no output on TX.

Recommended sequence:

1. `svd_load(...)`
2. `diagnose("UART2 has no output", peripheral="USART2")`
3. `svd_read_peripheral("USART2")`
4. `svd_read_peripheral("RCC")`
5. If needed, inspect GPIO AFR/MODER registers

Most important fields:

- RCC clock enable bits
- USART enable bits
- GPIO mode / AF fields

Interpretation notes:

- Missing UART output is often a clock-enable or alternate-function issue, not a logic bug in application code.

## 4. FreeRTOS Task Appears Stuck

User problem:

> A FreeRTOS task seems stuck and the system stops making progress.

Recommended sequence:

1. `read_rtt_log()`
2. `list_rtos_tasks()`
3. `rtos_task_context(...)`
4. `read_stack_usage()`
5. If needed, `diagnose("task is stuck")`

Most important fields:

- task name
- state
- `pc_symbol`
- `source`
- stack free bytes / canary usage

Interpretation notes:

- A blocked task is not necessarily broken; use its wait function and source location to tell the difference between healthy waiting and pathological stalling.

## 5. J-Link RTT Validation

User problem:

> Check whether RTT is working on a J-Link-connected board.

Recommended sequence:

1. `get_target_info(target, backend="jlink")`
2. `configure_probe(backend="jlink", ...)`
3. `probe_connect(...)`
4. `read_rtt_log(channel=0)`
5. If needed, run `scripts/jlink_rtt_smoke.py`

Most important fields:

- `status`
- `summary`
- `text`
- `cb_address`
- `buffer_size`

Interpretation notes:

- Detecting the control block is not the same as capturing text.
- Empty text can still mean the firmware has not emitted a line yet, especially early in boot.
