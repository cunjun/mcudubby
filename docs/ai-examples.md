# AI Examples

These examples show compact evidence-first requests. Exact tool signatures live in the [tool reference](tool-reference.md).

## Connect and baseline

```text
doctor()
first_contact()
list_connected_probes()
match_chip_name(target="STM32F103C8")
configure_probe(backend="pyocd")
probe_connect(target="target-name")
probe_reset(halt=True)
read_stopped_context()
```

Expected report: probe ID, backend target, stop reason, core registers, errors, and the next missing evidence.

## Boot failure

```text
collect_startup_evidence()
```

If fault state is present:

```text
collect_crash_evidence()
backtrace()
```

Ask the AI to distinguish reset-loop evidence, invalid vectors, fault registers, and missing-symbol uncertainty.

## Crash with symbols

```text
configure_elf(elf_path="build/firmware.elf")
elf_load(path="build/firmware.elf")
collect_crash_evidence()
backtrace()
```

Confirm that the ELF matches the flashed image before accepting function names or source lines.

## Silent peripheral

```text
svd_load(svd_path="device.svd")
collect_peripheral_evidence(peripheral="USART1")
svd_read_peripheral(peripheral="RCC")
svd_read_peripheral(peripheral="GPIOA")
svd_read_peripheral(peripheral="USART1")
```

Separate clock enable, pin mux, peripheral configuration, interrupt state, bus activity, and physical output. A firmware ACK proves only that a command path responded.

## RTOS stall

```text
collect_rtos_evidence()
list_rtos_tasks()
rtos_task_context(task_name="worker")
```

Report scheduler state, blocked/runnable tasks, suspicious stacks, and whether task metadata was decoded reliably.

## RTT/UART logs

```text
read_rtt_log()
log_tail(lines=100)
```

Include capture backend, channel/port settings, timestamps when available, truncation, decode errors, and whether an empty result means silence or missing configuration.

## Full-profile path proof

Enable `MCUBUDDY_TOOL_PROFILE=full` before server startup, then use a deliberately chosen execution-control call:

```text
run_to_function(function="main")
run_to_source(file="app.c", line=120)
source_step()
```

State how execution was changed and re-collect stopped context afterward.

## Result envelope

McuBuddy results should be interpreted structurally rather than from a single text field. A typical response contains status, data/evidence, errors or warnings, and metadata.

```json
{
  "ok": true,
  "data": {"example": "evidence"},
  "warnings": [],
  "errors": [],
  "meta": {"tool": "example_tool"}
}
```

Rules for AI clients:

- `ok: false` means the requested operation did not complete; do not invent missing evidence.
- Warnings qualify the result and belong in the report.
- Empty data is not automatically proof of absence.
- Preserve raw register values alongside decoded interpretation.
- Keep facts, hypotheses, and proposed actions in separate sections.

## Safe flash comparison

Before persistent changes, confirm target, firmware path, and intent. After programming, compare the intended ELF/image with flash, reset/halt, and collect fresh evidence under the same conditions.
