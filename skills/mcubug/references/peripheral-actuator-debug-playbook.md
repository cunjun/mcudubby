# Peripheral Actuator Debug Playbook

Use this playbook when firmware can talk to a peripheral, but the physical actuator still does
not move. Typical examples are I2C/SPI motor drivers, valve drivers, relay drivers, LED drivers,
and power-switch ICs.

The goal is to avoid stopping too early at "the function was called". A useful debug session must
separate four layers:

1. firmware path
2. bus transaction
3. peripheral internal state
4. power/output/load path

## What This Case Taught Us

In the STM32F429 + I2C2 + MS35229 stepper case, McuBubby proved:

- the motion API was reached with the expected argument
- I2C2 communication was healthy
- the chip ID read back correctly
- the start command was ACKed
- the driver status register reported `motorRunning`
- the sleep pin was high

That moved the likely fault away from `main.c` and toward output current, motor wiring, driver
power stage, or motor-driver configuration.

This is the pattern to reuse.

## Evidence Ladder

### 1. Confirm The Firmware Path

Use this only as the first rung, not the conclusion.

Collect:

- breakpoint hit at the requested API
- function argument registers
- caller/source location
- whether an early return path was taken

Example interpretation:

- Good: `MotorA_Stepper_Reverse` hit with `r0 = 0x7d0`, so the user request reached firmware.
- Not enough: this does not prove the peripheral accepted or executed the command.

### 2. Confirm The Bus Transaction

Collect:

- last register address and value written
- HAL/backend status
- peripheral bus status flags, such as I2C ACK failure, bus error, arbitration lost, or busy stuck
- chip ID or a stable read-only register

For I2C motor drivers, add temporary firmware "black box" globals when needed:

```c
volatile uint8_t g_dbg_lastReg;
volatile uint8_t g_dbg_lastValue;
volatile uint8_t g_dbg_lastHalStatus;
volatile uint8_t g_dbg_chipId;
```

These are low-risk because they observe existing transactions without changing motion behavior.

### 3. Confirm Peripheral Internal State

Do not rely only on write success. Read back status after the command.

Collect:

- command/control register
- status register
- fault/flag register
- interrupt pin level
- enable/sleep pin level

Useful questions:

- Did the status register report "running", "busy", or "fault"?
- Did the interrupt pin assert?
- Did the command cache reject the new command?
- Did the enable/sleep pin remain in the active state?

If the peripheral reports "running" but the actuator does not move, stop blaming the call path.
Move to output/load evidence.

### 4. Confirm Power, Output, And Load Path

Collect with hardware-safe methods:

- motor/actuator supply voltage under load, not only idle voltage
- enable pin voltage at the driver IC
- coil/load continuity
- connector pinout and phase order
- driver output waveform/current with a scope or current probe
- thermal/fault indication after a short command

Avoid jumping directly to maximum current. Increase current in small steps and keep motion pulses
short until output behavior is understood.

## Safe Debug Rules

- Prefer breakpoints before motion commands when experimenting with new firmware.
- Use short pulse counts or short run windows first.
- Add read-only instrumentation before changing current, PWM duty, or force.
- Stop or sleep the driver after a halted breakpoint if the target was paused before a stop command.
- Record exact register values and pin levels in the final diagnosis.

## Useful McuBubby Improvements

The current manual workflow works, but these features would make actuator debugging faster:

- `watch_symbols(...)`: read a named list of globals each time a breakpoint hits.
- `run_to_then_snapshot(...)`: set a breakpoint, run, then atomically read registers, memory, and pins.
- `i2c_health_snapshot(...)`: decode common STM32 I2C flags like `BUSY`, `AF`, `BERR`, `ARLO`, `OVR`.
- `gpio_pin_snapshot(...)`: read and label a small set of GPIO input/output levels.
- `peripheral_blackbox_template(...)`: generate C snippets for safe volatile debug globals.
- `actuator_diagnose(...)`: guide the AI through firmware path, bus, peripheral state, and output/load.

## Final Answer Template

When reporting findings, separate evidence from suspicion:

```text
Evidence:
- API reached with expected argument.
- Last command write succeeded.
- Chip ID/status register read back correctly.
- Driver status says running.

Conclusion:
The firmware and bus layers are likely working. The remaining likely causes are current setting,
output stage, wiring/phase order, load supply under motion, or driver fault behavior.

Next safe test:
Try one small configuration change or one hardware measurement, not several at once.
```

