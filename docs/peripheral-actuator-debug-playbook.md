# Peripheral and Actuator Debugging

Use this playbook when firmware acknowledges a command but a motor, relay, heater, LED, valve, or other output does not behave as expected. An ACK confirms only part of the software path.

## Four-layer evidence ladder

### 1. Firmware path

- Confirm the command handler ran.
- Inspect mode, guards, error flags, and requested output values.
- Use stopped context, symbols, logs, and breakpoints before modifying state.

Question answered: did firmware request the action?

### 2. Bus or driver transaction

- Inspect queued frames, DMA state, SPI/I2C/UART status, chip-select, and completion/error flags.
- Distinguish “API returned” from “transaction completed.”

Question answered: did the request reach the peripheral or external driver?

### 3. MCU peripheral and pin state

```text
svd_load(svd_path="device.svd")
collect_peripheral_evidence(peripheral="TIM1")
svd_read_peripheral(peripheral="RCC")
svd_read_peripheral(peripheral="GPIOA")
svd_read_peripheral(peripheral="TIM1")
```

Check clock gates, alternate-function selection, enable bits, compare values, interrupt/DMA state, and status flags.

Question answered: is the MCU configured to produce the expected signal?

### 4. Physical output and load

- Measure voltage, PWM, current, enable/fault pins, and supply rails.
- Check driver faults, interlocks, connectors, mechanics, and load conditions.

Question answered: did electrical energy reach the load safely?

## Interpretation rules

- A command ACK does not prove a pin toggled.
- A peripheral enable bit does not prove a waveform exists.
- A waveform does not prove the driver is powered or the load can move.
- Record where evidence stops; do not collapse all layers into “hardware failure.”

## Safety

Start with read-only evidence. For energized tests, use short duration, low duty/energy, a safe mechanical setup, and an accessible shutdown. Confirm target and address before writes; avoid repeated resets or flash cycles when they can activate outputs.

## Report

For each layer, state observed evidence, what it proves, what remains unknown, and the smallest safe next check.
