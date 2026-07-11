# Windows MCP Config Example

This document shows how to register `mcudubby` as an MCP server on Windows. It only covers client
launch configuration; use [Quickstart](quickstart.md) for the first board workflow.

## Before You Configure MCP

Confirm these first:

1. the `mcudubby` repository or package is installed
2. the Python environment can import `mcudubby`
3. the board can be reached by the chosen probe outside the MCP client
4. optional UART or RTT logging works when your workflow depends on logs

## Choose A Working Directory

If you are running from a source checkout, use the repository root as `cwd`. That is the directory
containing `pyproject.toml` and `src/mcudubby`.

Example placeholder:

```text
E:\work_code\mcudubby
```

Replace this path with your local checkout path.

## Recommended Launch Commands

Windows Python environments vary, so these are the common choices:

```text
py -3 -m mcudubby
python -m mcudubby
mcudubby
```

Start with `py -3 -m mcudubby` if the Python launcher is installed. Use an explicit virtualenv
Python path when the MCP client does not inherit your shell environment.

## Minimal Config With Python Launcher

```json
{
  "mcpServers": {
    "mcudubby": {
      "command": "py",
      "args": ["-3", "-m", "mcudubby"],
      "cwd": "E:\\work_code\\mcudubby"
    }
  }
}
```

If your MCP client does not support `cwd`, install the package into a globally resolvable Python
environment or point directly at a virtualenv Python.

## Alternative Config With `python`

```json
{
  "mcpServers": {
    "mcudubby": {
      "command": "python",
      "args": ["-m", "mcudubby"],
      "cwd": "E:\\work_code\\mcudubby"
    }
  }
}
```

## Editable Install

Use this when you want the MCP client to run local source edits:

```powershell
py -3 -m pip install -e .
```

Run it from the repository root. If `python` is the command bound to your desired environment,
use:

```powershell
python -m pip install -e .
```

## Virtual Environment Config

Create and install into a local virtual environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install -e .
```

Then point the MCP client at that Python executable:

```json
{
  "mcpServers": {
    "mcudubby": {
      "command": "E:\\work_code\\mcudubby\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcudubby"],
      "cwd": "E:\\work_code\\mcudubby"
    }
  }
}
```

This is often the most stable option on Windows because the client and the shell use the same
installed dependencies.

## First Workflow After Registration

Once the client can see the server, continue with [Quickstart](quickstart.md). The first check is
usually:

```text
list_connected_probes()
list_supported_targets("pyocd")
```

Then configure the target, symbols, optional logs, and run `board_smoke_test()`.

## If Server Launch Fails

If `py -3 -m mcudubby` fails:

- confirm the Python launcher is installed
- confirm editable install completed
- run the same command in a terminal from the configured `cwd`

If import fails:

- install from the repository root or from PyPI
- confirm dependencies are installed in the same Python environment
- point the MCP client at the exact virtualenv Python when needed

If the server starts but tools fail:

- confirm `pyocd`, `pyserial`, and optional J-Link dependencies exist in that environment
- confirm the probe is not owned by another debugger
- confirm target power, wiring, reset, and probe serial selection
