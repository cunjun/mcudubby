# Quickstart

This guide shows the shortest path from an installed `McuBuddy` server to the first real-board
debug session.

## 1. Install

```bash
pip install McuBuddy
```

From a local checkout:

```bash
pip install -e .
```

Install optional development dependencies when running tests:

```bash
pip install -e ".[dev]"
```

## 2. Configure MCP

Before editing your MCP client config, run the local management checks:

```bash
McuBuddy doctor
McuBuddy config generate > mcubuddy.toml
McuBuddy config validate mcubuddy.toml
McuBuddy probes list
```

Use `--json` with `doctor` or `probes list` when sharing machine-readable setup details in an
issue or support thread.

McuBuddy v0.6 starts in the `core` tool profile by default. This keeps the MCP schema small and
focuses the model on bring-up, evidence collection, peripheral/RTOS/log inspection, and
build/flash/verify loops.

For Claude Desktop / Claude Code:

```json
{
  "mcpServers": {
    "McuBuddy": {
      "command": "python",
      "args": ["-m", "McuBuddy"]
    }
  }
}
```

Use the virtual-environment Python path if your MCP client does not inherit the shell
environment.

To expose the full expert catalog from v0.5.x, opt in explicitly and restart the MCP server:

```json
{
  "mcpServers": {
    "McuBuddy": {
      "command": "python",
      "args": ["-m", "McuBuddy"],
      "env": {
        "MCUBUDDY_TOOL_PROFILE": "full"
      }
    }
  }
}
```

`full` is useful for low-level memory/register writes, advanced breakpoints, GDB server lifecycle,
legacy high-level diagnosis, and experimental trace tools. Before changing profiles, disconnect
active probes or log channels and restart the MCP server; the active profile cannot be expanded from
inside an existing MCP session.

## 3. Discover hardware

From a terminal, you can check probe discovery before starting an MCP client:

```bash
McuBuddy probes list
```

Inside the MCP session, use:

```python
list_connected_probes()
list_supported_targets("pyocd")
```

For `PY32F030X8` with CMSIS-DAP, use the built-in profile and set the probe ID:

```python
load_demo_profile("py32f030x8_cmsis_dap")
configure_probe(unique_id="LU_2022_8888")
```

For other pyOCD targets that come from a CMSIS-Pack, configure the pack path:

```python
configure_probe(
    target="PY32F030X8",
    backend="pyocd",
    unique_id="LU_2022_8888",
    pack_path=r"E:\work_code\McuBuddy\packs\Puya.PY32F0xx_DFP.1.2.8.pack",
    connect_attempts=[
        {"frequency": 100000, "connect_mode": "attach"},
        {"frequency": 100000, "connect_mode": "under-reset"},
    ],
)
```

When the Puya pack is stored under a local `packs/` directory, McuBuddy can auto-discover it
for `PY32F030X8`.

For built-in pyOCD targets, `pack_path` is optional:

```python
configure_probe(target="stm32l496vetx", backend="pyocd")
```

For J-Link:

```python
configure_probe(target="STM32F103C8", backend="jlink", unique_id="240710115")
```

## 4. Configure symbols

For a known ELF/AXF:

```python
configure_elf(r"E:\work_code\app\Objects\Project.axf")
```

For a Keil MDK project:

```python
discover_keil_projects(r"E:\work_code\app")
configure_keil_project(
    root=r"E:\work_code\app",
    uv4_path=r"E:\Keil_v5\UV4\UV4.exe",
)
```

## 5. Run a smoke test

```python
board_smoke_test()
```

Expected evidence is a connected probe, readable CPU state, and readable vector-table words.
The default flow connects to and halts the target and may leave it halted. Use
`board_smoke_test(disconnect_after=True)` when the probe should disconnect afterward.
If the probe is found but SWD returns `No ACK`, reduce the frequency, try `under-reset`, and
check target power, wiring, reset, and whether another debugger owns the probe.

## 6. Debug

```python
probe_halt()
read_stopped_context()
diagnose("board does not boot")
run_to_function("main")
```

Optional UART log setup:

```python
configure_log(uart_port="COM5", uart_baudrate=115200)
connect_with_config()
log_tail()
```

## 7. Safety Configuration

The generated `mcubuddy.toml` includes conservative defaults for destructive operations:

```toml
[memory]
max_read_size = 4096
max_write_size = 1024
allow_write = false

[flash]
allow_erase = false
allow_program = true
max_binary_size = 16777216

[security]
allowed_file_paths = []
```

Keep these defaults for first contact. Enable memory writes or flash erase only for a known board,
known firmware, and a workflow where the risk is intentional.
