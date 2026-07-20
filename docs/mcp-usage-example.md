# MCP Usage Example

This document shows a compact `McuBubby` MCP session after the server has already been registered
in an MCP client. For installation and client configuration, use [Quickstart](quickstart.md) and
[Windows MCP Config Example](windows-mcp-config-example.md).

## Recommended Flow

The first useful session should:

1. inspect available probes and target metadata
2. configure the probe
3. configure symbols and optional logs
4. run a read-only smoke test
5. collect stopped CPU context
6. run a symptom-driven diagnosis
7. fall back to lower-level tools when the diagnosis needs more evidence

## Minimal Session

For a built-in pyOCD target:

```text
list_connected_probes()
get_target_info("stm32l496vetx", backend="pyocd")
configure_probe(target="stm32l496vetx", backend="pyocd")
configure_elf("path/to/firmware.axf")
board_smoke_test()
probe_halt()
read_stopped_context()
diagnose("board does not boot")
```

For a J-Link target:

```text
get_target_info("STM32F103C8", backend="jlink")
configure_probe(target="STM32F103C8", backend="jlink", unique_id="240710115")
configure_elf("path/to/firmware.elf")
board_smoke_test()
read_rtt_log(channel=0)
```

For a CMSIS-Pack target:

```text
configure_probe(
  target="PY32F030X8",
  backend="pyocd",
  unique_id="LU_2022_8888",
  pack_path="path/to/Puya.PY32F0xx_DFP.1.2.8.pack",
  connect_attempts=[
    {"frequency": 100000, "connect_mode": "attach"},
    {"frequency": 100000, "connect_mode": "under-reset"}
  ]
)
board_smoke_test()
```

## Optional UART Log Setup

If the firmware prints startup progress through UART:

```text
configure_log(uart_port="COM5", uart_baudrate=115200)
connect_with_config()
log_tail(20)
```

Expected evidence might look like:

```text
boot start
clock init ok
uart init ok
sensor init...
```

If logs stop at a specific stage and the CPU is halted in a fault handler, continue with:

```text
diagnose_startup_failure()
diagnose_hardfault()
backtrace()
```

## Result Shape

A useful human-readable diagnosis separates observations from conclusions:

```text
Evidence:
- UART output stops after "sensor init...".
- The target is currently in HardFault_Handler.
- Fault registers indicate a precise data bus fault.
- The loaded ELF resolves the failing path to sensor initialization.

Conclusion:
The failure is likely in early sensor setup, such as an invalid pointer or incorrect register
access. Inspect the init function arguments, faulting address, and nearby peripheral state next.
```

## When To Use Manual Tools

If high-level diagnosis looks incomplete, use lower-level tools to separate:

- wiring or target-power issues
- UART setup issues
- probe attach issues
- symbol or ELF mismatch
- diagnosis logic issues

Useful fallback tools:

```text
probe_read_registers()
probe_halt()
probe_reset(halt=True)
read_stopped_context()
log_tail(50)
svd_read_peripheral("RCC")
```

For scenario-specific flows, use [AI Examples](ai-examples.md).
