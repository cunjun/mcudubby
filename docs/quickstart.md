# Quickstart

This guide gets one McuBuddy MCP session from installation to its first structured hardware evidence.

## 1. Requirements

- Python 3.11+
- A supported probe and driver
- A target name accepted by the selected backend
- Optional ELF and SVD files for symbols and peripheral decoding

## 2. Install

```bash
git clone <repository-url>
cd McuBuddy
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -e .
```

## 3. Validate runtime and configuration

Run the management preflight before starting an MCP client or touching hardware:

```text
McuBuddy doctor --json
McuBuddy config generate > mcubuddy.toml
McuBuddy config validate mcubuddy.toml
McuBuddy config show --json
McuBuddy probes list --json
```

For PY32F030X8, diagnose or explicitly install the trusted device pack:

```powershell
McuBuddy packs diagnose PY32F030X8 --json
McuBuddy packs install PY32F030X8 --confirm --json
```

Configuration precedence is defaults, then TOML, then `MCUBUDDY_*` environment variables, then
CLI `--set SECTION.FIELD=VALUE` overrides. Keep memory writes and flash erase disabled until a
specific workflow requires them. RTT scanning is bounded by `security.max_rtt_scan_size`; use
`MCUBUDDY_MAX_RTT_SCAN_SIZE` only to set an intentional, board-appropriate limit.

## 4. Configure the MCP client

Windows example:

```json
{
  "mcpServers": {
    "mcubuddy": {
      "command": "C:\\path\\to\\McuBuddy\\.venv\\Scripts\\McuBuddy.exe",
      "args": [],
      "cwd": "C:\\path\\to\\McuBuddy"
    }
  }
}
```

For environment variables and alternate launchers, see [Windows MCP configuration](windows-mcp-config-example.md). Restart the MCP client after changing its configuration.

## 5. Choose a profile

<!-- mcubuddy-profile: core -->
The default `core` profile is sufficient for discovery, connection, read-only inspection, evidence packages, and common build/flash entry points. Begin here.
<!-- /mcubuddy-profile -->

<!-- mcubuddy-profile: full -->
Set `MCUBUDDY_TOOL_PROFILE=full` before server startup only when you need specialized diagnosis, smoke tests, fine-grained stepping, run-to-location, or other advanced controls.
<!-- /mcubuddy-profile -->

## 6. Discover and connect

Ask McuBuddy to resolve the backend target name if necessary:

```text
list_connected_probes()
match_chip_name(target="PY32F030")
get_target_info(target="py32f030x8")
```

Configure the backend and connect:

```text
configure_probe(backend="pyocd")
probe_connect(target="py32f030x8")
```

Use `unique_id` when multiple probes are attached. If connection is unstable, lower the SWD speed, check target power/wiring/reset, and close other debugger processes.

Inside the MCP session, begin with the core preflight:

```text
doctor()
first_contact()
```

## 7. Collect first evidence

Establish a known stopped state before interpreting registers or memory:

```text
probe_reset(halt=True)
read_stopped_context()
collect_startup_evidence()
```

For a crash:

```text
collect_crash_evidence()
backtrace()
```

Treat returned facts as evidence. Keep hypotheses separate until registers, stack, symbols, logs, or peripheral state support them.

## 8. Add symbols and SVD data

Configure an ELF used by project workflows:

```text
configure_elf(elf_path="build/firmware.elf")
```

Load it into the current debug session:

```text
elf_load(path="build/firmware.elf")
```

Load a peripheral description when clock or peripheral state matters:

```text
svd_load(svd_path="device.svd")
svd_read_peripheral(peripheral="RCC")
```

## 9. Keep session operations ordered

One McuBuddy server session is one hardware-debug channel. Await reset, halt, resume, memory access, backend configuration, build, flash, and disconnect calls. Use separate sessions for independent boards.

## 10. Next routes

- Unknown/custom board: [Generic board workflow](generic-board-workflow.md)
- AI-driven diagnosis: [AI debugging playbook](ai-playbook.md)
- Exact commands: [Tool reference](tool-reference.md)
- Backend limits: [Support matrix](support-matrix.md)
- Real-board qualification: [Board validation guide](board-validation-guide.md)

## Troubleshooting

- No tools visible: restart the MCP client and inspect server stderr.
- Probe missing: verify drivers, USB permissions, cables, and competing debugger processes.
- Target rejected: use `match_chip_name(...)` and the backend-canonical name.
- Symbols absent: confirm the ELF contains debug information and belongs to the flashed image.
- Peripheral names absent: load the correct SVD for the device family.
