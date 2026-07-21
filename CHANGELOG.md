# Changelog

## 0.6.0 - 2026-07-20

### Changed
- Switched the default MCP tool profile to `core`, exposing a smaller evidence-first tool set.
- Added explicit `MCUBUDDY_TOOL_PROFILE=full` opt-in for the complete legacy tool surface plus
  the new evidence collectors.
- Made `list_tool_safety` report the active profile and hide non-exposed tool metadata by default.

### Added
- Added `collect_crash_evidence`, `collect_startup_evidence`, `collect_peripheral_evidence`, and
  `collect_rtos_evidence` as structured evidence package entry points.
- Added a repeatable GPT-5.6 tool-surface evaluation scenario file and baseline notes.

### Migration
- This is a breaking default-behavior change for alpha users. Existing clients that relied on the
  full 0.5.x tool catalog should set `MCUBUDDY_TOOL_PROFILE=full` in their MCP server environment.

## 0.5.1 - 2026-07-20

### Changed
- Standardized the project, Python package, command, documentation, and Rust sidecar branding as
  `McuBuddy`.
- Added PyPI ownership metadata and `server.json` for publishing McuBuddy to the official MCP
  Registry.
- Excluded local build caches from source distributions and added registry metadata validation.

## 0.5.0 - 2026-07-17

### Changed
- Moved blocking MCP tool execution to worker threads so probe and backend calls do not block the
  MCP event loop.
- Serialized operations that share a debug session while keeping independent sessions and
  stateless metadata queries concurrent.
- Kept session locks held until cancelled worker calls finish, preventing backend replacement or a
  second probe command from overlapping an in-flight operation.
- Preserved all 104 MCP tool names, parameters, and schemas across the execution-boundary refactor.
- Centralized MCP tool safety and execution policies, including explicit confirmation for DWT/SWO
  activation and diagnosis commands that can change target execution state.
- Made probe reconfiguration transactional so invalid connection attempts cannot replace the
  active backend or partially mutate the current configuration.

## 0.4.0 - 2026-07-11

### Released
- Published the initial `McuBuddy` v0.4.0 release.

## 0.2.0 - 2026-04-01

### Added
- SVD peripheral register support (Phase 2)
  - `SvdManager`: load CMSIS-SVD files, parse peripheral/register/field definitions
  - `svd_load`, `svd_list_peripherals`, `svd_get_registers`, `svd_read_peripheral` MCP tools
  - Field-level register decoding for all peripherals
  - Automatic diagnosis for UART, SPI, I2C, GPIO peripherals
  - Handles malformed SVD register names via offset-based alias fallback
- New probe tools: `list_connected_probes`, `probe_step`, `probe_write_memory`
- Split `configure_target` into focused tools: `configure_probe`, `configure_log`, `configure_elf`, `configure_build`

### Validated
- Real STM32L496VETx board: USART1 register state read at 115200 baud
- SVD loaded from Keil STM32L4xx_DFP pack (85 peripherals)

## 0.1.0 - 2026-03-31

### Added
- `pyOCD` probe backend: connect, halt, resume, reset, read registers, read memory, breakpoints
- UART log backend: connect, disconnect, tail
- ELF/AXF symbol resolution via `pyelftools`
- `diagnose_hardfault`: Cortex-M fault register analysis with structured evidence
- `diagnose_startup_failure`: startup stage analysis
- `run_debug_loop`: AI-driven multi-step debug loop
- Keil UV4 build and flash integration
- Demo profiles and mock backends for offline development
- Real hardware validation on STM32L496VETx with ST-Link
