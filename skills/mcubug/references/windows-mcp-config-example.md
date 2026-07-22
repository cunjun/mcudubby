# Windows MCP Configuration

Use generic absolute paths and adjust them to the local checkout. Do not copy another user's home or workspace path.

## Direct virtual-environment launch

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

This is the preferred Windows setup because it does not depend on shell activation.

## Enable the full profile

The default profile is `core`. Add an environment variable only when advanced tools are required:

```json
{
  "mcpServers": {
    "mcubuddy": {
      "command": "C:\\path\\to\\McuBuddy\\.venv\\Scripts\\McuBuddy.exe",
      "args": [],
      "cwd": "C:\\path\\to\\McuBuddy",
      "env": {
        "MCUBUDDY_TOOL_PROFILE": "full"
      }
    }
  }
}
```

Restart the MCP client after changing the profile; an already-running server keeps its existing tool set.

## Using a module launcher on PATH

If the intended Python environment is already stable and explicit:

```json
{
  "mcpServers": {
    "mcubuddy": {
      "command": "McuBuddy",
      "args": [],
      "cwd": "C:\\path\\to\\McuBuddy"
    }
  }
}
```

Prefer the direct virtual-environment path when multiple Python installations exist.

## Verification

From PowerShell:

```powershell
& 'C:\path\to\McuBuddy\.venv\Scripts\python.exe' -c "import McuBuddy; print('McuBuddy import OK')"
& 'C:\path\to\McuBuddy\.venv\Scripts\McuBuddy.exe' doctor --json
& 'C:\path\to\McuBuddy\.venv\Scripts\McuBuddy.exe' config show --json
```

Then restart the client and confirm that McuBuddy tools appear. A minimal hardware sequence is:

```text
doctor()
first_contact()
list_connected_probes()
configure_probe(backend="pyocd")
probe_connect(target="target-name")
read_stopped_context()
```

## Common failures

- `python` resolves to the wrong interpreter: use the absolute `.venv` executable.
- Server starts then exits: inspect MCP server stderr and verify editable installation.
- Tools do not change after setting the profile: fully restart the client/server process.
- Probe is busy: close Keil, GDB servers, vendor utilities, and other McuBuddy sessions.
- JSON path escaping fails: use doubled backslashes as shown above.
