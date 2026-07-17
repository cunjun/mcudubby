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

## MCP Execution Boundary

`src/mcudubby/mcp_execution.py` wraps every registered MCP tool before FastMCP exposes it.
Tool callbacks run in worker threads so blocking probe SDK, sidecar, filesystem, and build calls
do not block the MCP event loop.

Tools that access a shared `SessionState` are serialized by that session's execution lock. This
keeps probe operations, backend replacement, ELF/SVD state, logs, and runtime configuration from
overlapping within one debug session. Separate sessions have separate locks and may execute in
parallel. Stateless metadata queries such as target matching and tool-safety discovery bypass the
session lock, but still run outside the event loop.

Cancellation does not stop a synchronous SDK call that is already running in a worker thread.
The execution boundary therefore holds the session lock until that worker finishes, then propagates
the cancellation. Keep this invariant when adding new execution paths; releasing the lock early can
allow a second command to mutate or disconnect a backend that is still in use.

The execution wrapper preserves each registered function's name, signature, documentation, and MCP
schema. New tools should continue to use the normal `@mcp.tool()` registration pattern rather than
calling the execution boundary directly.

## Domain Tools

`src/mcudubby/tools/` contains behavior-oriented modules that can be tested without MCP.
Keep public compatibility modules as small re-export layers when a domain becomes a package.

The experimental `probe-rs` backend uses `rust/probe-sidecar/` as a hardware execution sidecar.
Python remains the owner of MCP, sessions, diagnosis, ELF/DWARF, SVD, and RTOS semantics. The
sidecar owns probe-rs sessions and exchanges versioned, newline-delimited JSON-RPC messages over
stdio. Keep this protocol internal; it is not a second MCP surface.

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
