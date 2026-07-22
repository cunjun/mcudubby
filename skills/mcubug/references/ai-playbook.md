# AI Debugging Playbook

Use McuBuddy as an evidence collector, not as permission to guess. Keep the board in a known state, collect the smallest decisive evidence set, and label interpretation separately.

## Decision order

1. Identify the exact target, probe, backend, firmware, and symptom.
2. Decide whether the next call is read-only, execution-changing, state-changing, or persistent.
3. Establish a known stopped state when register or memory consistency matters.
4. Start with the symptom-specific evidence package.
5. Add ELF, SVD, RTOS, or log evidence only when it can distinguish competing explanations.
6. Change execution or device state only with a clear reason.
7. Re-collect the same evidence after a fix so the comparison is meaningful.

## Start a session

<!-- mcubuddy-profile: core -->
```text
doctor()
first_contact()
match_chip_name(target="device marking")
configure_probe(backend="pyocd")
probe_connect(target="target-name")
probe_reset(halt=True)
read_stopped_context()
```

The default `core` profile covers the standard evidence-first flow.
<!-- /mcubuddy-profile -->

<!-- mcubuddy-profile: full -->
Enable `MCUBUDDY_TOOL_PROFILE=full` before server startup for specialized diagnosis, board smoke tests, run-to-location, or fine source stepping. Explain why the expanded tool surface is needed.
<!-- /mcubuddy-profile -->

## Route by symptom

| Symptom | First evidence | Useful additions |
| --- | --- | --- |
| Board does not boot | `collect_startup_evidence(...)` | reset state, logs, then crash evidence if faulted |
| HardFault/crash | `collect_crash_evidence(...)` | `backtrace()`, matching ELF, stack memory |
| UART/SPI/I2C/GPIO silent | `collect_peripheral_evidence(...)` | SVD clock, GPIO, peripheral and NVIC state |
| RTOS stall | `collect_rtos_evidence(...)` | task list/context, logs, selected stacks |
| Intermittent corruption | crash evidence and snapshots | full profile adds specialized diagnosis/watchpoints |
| Clock suspicion | RCC/SVD evidence | full profile adds specialized clock diagnosis |
| Need path proof | stopped context and breakpoints | full profile adds run-to/source stepping |

Do not enumerate every tool in this playbook; use the [tool reference](tool-reference.md) for exact signatures.

## Evidence quality

Strong evidence is reproducible and tied to board state:

- exact backend target and probe ID
- firmware/ELF identity
- stop reason and core registers
- decoded fault status plus raw values
- symbol/source mapping from the matching ELF
- SVD register values from the exact device
- log timestamps and capture configuration
- before/after evidence collected with the same procedure

Weak evidence includes successful configuration without hardware contact, stale symbols, a lone ACK, inferred peripheral behavior, or a passing host-side test presented as board validation.

## Hypothesis loop

For each plausible cause:

```text
Hypothesis: what could explain the symptom?
Prediction: what evidence would be present if true?
Check: smallest safe tool call that distinguishes it?
Result: observed facts, including uncertainty or tool errors.
Decision: keep, reject, or refine the hypothesis.
```

Prefer checks that separate several hypotheses at once. Stop collecting when the evidence already decides the next safe action.

## Symbols and peripheral data

```text
configure_elf(elf_path="build/firmware.elf")
elf_load(path="build/firmware.elf")
svd_load(svd_path="device.svd")
```

Never trust source lines or variable locations until the ELF is known to match the flashed firmware. Never trust an SVD register interpretation until the device and revision are confirmed.

## Stateful ordering

Await all operations that share probe, backend, ELF/SVD, log, build, or runtime configuration. Cancellation may not interrupt an underlying synchronous probe call. Use separate server sessions for separate boards rather than racing commands in one session.

## Safety escalation

- Read-only: metadata, registers, memory, evidence packages, logs
- Execution-changing: reset, halt, resume, stepping, breakpoints/watchpoints
- State-changing: register and memory writes
- Persistent: erase, program, build-and-flash workflows

Confirm the exact target and intent before state-changing or persistent work. For motors, relays, heaters, or power switches, prefer breakpoints and read-only instrumentation, then short low-energy commands under safe physical conditions.

## Reporting

```text
Evidence:
- observed fact and source

Interpretation:
- what the evidence supports

Unknowns:
- missing or unreliable information

Next check:
- smallest safe discriminating action

Safety:
- state or hardware effects
```

Report tool failures as evidence gaps, not as proof that the firmware is healthy or faulty.
