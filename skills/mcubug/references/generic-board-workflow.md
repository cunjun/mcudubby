# Generic Board Workflow

Use this route when the board is new, the MCU name is ambiguous, or no project-specific automation exists.

## 1. Inventory the inputs

Record:

- MCU marking and board revision
- Probe type and serial/unique ID
- Debug backend preference
- SWD/JTAG wiring, target voltage, and reset availability
- Keil project, ELF, SVD, CMSIS-Pack, and expected firmware image

Do not infer the exact target from a marketing board name alone.

## 2. Resolve the target

```text
list_connected_probes()
match_chip_name(target="your MCU marking")
get_target_info(target="backend-canonical-name")
```

For pyOCD, target names are usually lower-case. J-Link uses its own device catalogue. If metadata is missing, install or point McuBuddy at the appropriate CMSIS-Pack before connecting.

## 3. Configure the probe and connect

```text
configure_probe(backend="pyocd")
probe_connect(target="your_mcu_name", unique_id="probe-id-if-needed")
```

Connection recovery order:

1. Confirm target power, ground, SWDIO/SWCLK, and reset.
2. Close Keil, GDB servers, and other probe owners.
3. Lower the configured SWD speed.
4. Try attach-under-reset when supported.
5. Re-check the backend target name and pack support.

## 4. Establish a baseline

```text
probe_reset(halt=True)
read_stopped_context()
collect_startup_evidence()
```

Record backend, probe ID, target name, core registers, stop reason, and any transport errors. This baseline separates connection failures from firmware failures.

## 5. Add project information

Keil project:

```text
configure_keil_project(project_path="firmware.uvprojx")
```

ELF configuration and session loading:

```text
configure_elf(elf_path="build/firmware.elf")
elf_load(path="build/firmware.elf")
```

Confirm the ELF matches the flashed build before trusting symbols, source lines, or globals.

## 6. Add peripheral evidence

```text
svd_load(svd_path="device.svd")
svd_read_peripheral(peripheral="RCC")
```

Use SVD evidence for clock gates, GPIO modes, interrupt enables, and peripheral status. Verify addresses against the exact MCU revision when vendor files are uncertain.

## 7. Route by symptom

| Symptom | First evidence |
| --- | --- |
| No boot | `collect_startup_evidence(...)` |
| Fault/crash | `collect_crash_evidence(...)`, `backtrace()` |
| Silent peripheral | `collect_peripheral_evidence(...)`, SVD reads |
| RTOS stall | `collect_rtos_evidence(...)`, task context |
| No logs | RTT/UART configuration, then log reads |

Specialized diagnosis and fine execution control require the `full` profile. Enable it only after the core evidence shows why it is needed.

## 8. Record validation

Use the [board validation guide](board-validation-guide.md). Store reproducible commands, structured result envelopes, firmware identity, and observed limitations; do not report a capability as supported from configuration alone.

## Safety

Reads are preferred first. Reset/halt/resume alter execution, register or memory writes alter state, and flash operations persist changes. Confirm target identity and intent before escalating.
