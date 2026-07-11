# Architecture

`mcudubby` is organized around three layers:

1. MCP application layer: `mcudubby.server` creates the FastMCP app and session.
2. MCP registration layer: `mcudubby.mcp_tools` exposes user-facing MCP tools by domain.
3. Domain tool layer: `mcudubby.tools` implements behavior without depending on MCP.

## Application Entry

`src/mcudubby/server.py` should stay small. It owns app creation and process startup only.
Do not add tool implementations or long registration blocks there.

## MCP Tool Registration

`src/mcudubby/mcp_tools/` contains one registration module per user-facing domain:

- `runtime.py`: configuration, profiles, first contact, and debug loop tools
- `build_debug.py`: build, flash, and GDB server lifecycle tools
- `io.py`: ELF loading, UART log tools, and disconnect lifecycle
- `svd.py`: SVD peripheral read/write tools
- `diagnostics.py`: high-level diagnosis tools
- `probe/`: probe tools split by control, memory, source, RTOS, symbols, trace, and watchpoints

Registration modules should be thin wrappers. They translate MCP parameters into calls to
domain tools and should not contain hardware logic.

## Domain Tools

`src/mcudubby/tools/` contains behavior-oriented modules that can be tested without MCP.
Keep public compatibility modules as small re-export layers when a domain becomes a package.

`src/mcudubby/tools/probe/` is the probe domain package:

- `core.py`: connection and basic target control
- `breakpoints.py` and `conditions.py`: breakpoint behavior
- `memory.py`, `memory_diagnostics.py`, and `flash.py`: memory and flash operations
- `execution.py`, `navigation.py`, `stack.py`, and `variables.py`: source-aware execution tools
- `rtos_*`: FreeRTOS-specific helpers and task tools
- `rtt.py`, `trace.py`, `watch.py`, and `symbols.py`: focused probe capabilities

Prefer adding new probe behavior to the closest existing module. Create a new module only when
the behavior has a distinct owner or would push an existing file beyond comfortable review size.

## File Size Guidance

Small, focused files are preferred, but do not split tightly coupled backend classes just to
reduce line count. Backend adapters such as `JLinkProbeBackend` and `PyOcdProbeBackend` may be
larger when the SDK integration is naturally class-centered.

As a rule of thumb:

- MCP registration files should stay under about 250 lines.
- Domain tool files should usually stay under about 350 lines.
- Larger backend/parser classes are acceptable when splitting would obscure state flow.
