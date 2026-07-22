# Board Validation Guide

This guide records reproducible real-board evidence. Configuration, mocks, and host-side tests do not prove hardware support.

## Required identity

Record the board/revision, MCU marking and backend target, probe model/ID, backend version, firmware build/hash, ELF/SVD/pack identity, and wiring/power/reset assumptions.

## Validation order

### A. Discover

```text
doctor()
first_contact()
list_connected_probes()
match_chip_name(target="device marking")
get_target_info(target="target-name")
```

Pass: the intended probe and an unambiguous target are recorded.

### B. Connect

```text
configure_probe(backend="pyocd")
probe_connect(target="target-name")
```

Pass: transport, core identity, and probe ownership are confirmed without unexplained warnings.

### C. Control and read

```text
probe_reset(halt=True)
read_stopped_context()
```

Pass: halt/reset and stable core-register reads are repeatable. Document these execution-state changes.

### D. Symbols and source

```text
configure_elf(elf_path="build/firmware.elf")
elf_load(path="build/firmware.elf")
backtrace()
```

Pass: the ELF matches flash and produces credible symbol/source context.

### E. Peripheral, logs, and RTOS

```text
svd_load(svd_path="device.svd")
collect_peripheral_evidence(peripheral="RCC")
read_rtt_log()
collect_rtos_evidence()
```

Run only applicable capabilities. Distinguish unsupported, not configured, and empty evidence.

### F. Persistent operations

Build/flash validation requires explicit authorization and a recoverable image. Record the image, address/range, verification method, and post-flash evidence. A successful return alone does not prove programming.

## Evidence record

```json
{
  "board": "board-name/revision",
  "target": "backend-target",
  "probe": "model-and-id",
  "backend": "pyocd",
  "firmware": {"build": "id", "sha256": "..."},
  "capability": "stopped-context",
  "result": "pass",
  "commands": ["probe_reset(halt=True)", "read_stopped_context()"],
  "evidence": "artifact-or-log-reference",
  "limitations": []
}
```

Results are `pass`, `fail`, `blocked`, or `not_applicable`; do not use vague percentages.

## Support-matrix update

Update [support-matrix.md](support-matrix.md) only from recorded evidence.

| Field | Meaning |
| --- | --- |
| Backend/target | Exact tested combination |
| Capability | Smallest independently proven behavior |
| Status | pass/fail/blocked/not applicable |
| Evidence | Stable artifact or validation record |
| Limits | Speed, reset mode, pack, firmware, or environment constraints |

## Failure handling

1. Preserve the raw result and transport errors.
2. Recheck power, wiring, reset, probe ownership, and target name.
3. Retry only after recording the changed condition.
4. Keep backend limitations separate from firmware defects.
5. Never turn a blocked check into a passing claim.

## Completion criteria

A board is validated only for exercised capabilities. Report identity, commands, criteria, evidence, execution/device-state changes, persistent changes, and remaining limits.
