# Support Matrix

This document summarizes what is implemented, what is hardware-validated, and where the current limits remain.

Machine-readable validation records live under `src/mcudubby/validation/` and are exposed through
`list_validation_records()`. Use those JSON files as the canonical evidence records, and keep this
page as the human-readable summary.

## Backend status

| Capability | pyOCD | J-Link | Notes |
|-----------|-------|--------|-------|
| Probe connect / halt / reset / resume / step | Yes | Yes | Hardware-validated on STM32L496VETx and STM32F103C8 |
| Source-level debug | Yes | Yes | `run_to_function`, `run_to_source`, `source_step`, `step_over`, `step_out` |
| Breakpoints / watchpoints | Yes | Yes | Hardware-validated on both main boards |
| Memory / register access | Yes | Yes | Includes FPU and fault registers |
| Flash erase / program / verify | Yes | Yes | Validated on scratch-sector workflows and active firmware images |
| RTT | Yes | Yes | J-Link uses native RTT first; pyOCD uses scan-based path |
| RTOS task listing / context | Yes | Partial | Primary full validation done on STM32L496VETx + ST-Link; J-Link path is not yet equivalently validated |
| GDB server lifecycle | Yes | Yes | pyOCD GDB server and J-Link GDB server both validated |
| DWT cycle counter | No current public path | Yes | Hardware-validated on STM32F103C8 + J-Link |
| SWO log read | No current public path | Partial | Backend path works; text capture depends on board wiring |

## Experimental probe-rs sidecar

The optional Rust sidecar currently provides an unvalidated `probe-rs` backend for probe discovery,
connection lifecycle, core control, core registers, memory access, and hardware breakpoints. It is
an integration preview rather than a hardware-validated backend. Flash, RTT, SWO, and packaged
release binaries are not yet part of this path.

## Hardware-validated targets

### ATK_PICTURE / STM32L496VETx / ST-Link

Record: `src/mcudubby/validation/stm32l496vetx-pyocd-stlink.json`

Validated:

- ELF / DWARF symbol and source mapping
- source-level stepping
- SVD register inspection and field writes
- flash erase / program / verify
- RTT log capture
- RTOS task list and task context
- `diagnose_*` flows
- pyOCD GDB server

Validated FreeRTOS synchronization patterns:

- queue
- binary semaphore
- software timer
- event group
- task notify
- mutex
- ISR-to-task notify

### Custom board / STM32F103C8 / J-Link

Record: `src/mcudubby/validation/stm32f103c8-jlink.json`

Validated:

- J-Link backend bring-up with DLL auto-discovery
- source-level stepping and function/source run-to flows
- flash erase / program / verify
- native RTT read path
- J-Link GDB server lifecycle
- DWT cycle counter

Partial:

- RTOS task listing / context has implementation coverage but is not yet a primary hardware-validated workflow on this board
- SWO host-buffer read path is implemented and callable
- firmware-side SWO configuration was validated
- text capture remained blocked by board-level `PB3/TRACESWO` constraints

## Target preflight support

`list_supported_targets(...)`, `match_chip_name(...)`, and `get_target_info(...)` currently include built-in profiles for:

- `stm32l496vetx` / `STM32L496VETx`
- `stm32f103c8` / `STM32F103C8`
- `stm32f103ze` / `STM32F103ZE`
- `py32f030x8` / `PY32F030X8`

Current preflight features:

- backend-specific target canonicalization
- connect fallback hints
- validation metadata
- warnings and recovery guidance
- lightweight non-intrusive post-connect state check
- local Puya `PY32F0xx` pack auto-discovery for `PY32F030X8`

## Generic target configuration

Targets do not need to be added as built-in profiles before they can be used. For pyOCD,
`configure_probe(...)` accepts local CMSIS-Pack paths and ordered connect attempts:

```python
configure_probe(
    target="vendor_target_id",
    backend="pyocd",
    pack_paths=[r"C:\path\Vendor.Device.1.0.0.pack"],
    connect_attempts=[
        {"frequency": 1000000, "connect_mode": "attach"},
        {"frequency": 100000, "connect_mode": "under-reset"},
    ],
)
```

Keil MDK project discovery is available through `discover_keil_projects(...)` and
`configure_keil_project(...)`. Use `board_smoke_test(...)` as the first real-board check
before flash, reset-heavy, or diagnosis workflows.

## Known limits

- SWO remains board-dependent even when the J-Link backend path itself is working.
- RTOS inspection assumes FreeRTOS symbols are present and consistent with the loaded ELF.
- Build/flash integration is still Keil UV4 centric on Windows.
- Device patching is intentionally lightweight; it is not yet a full plugin or per-board script system.
