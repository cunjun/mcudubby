# McuBuddy v0.6.0

McuBuddy v0.6.0 changes the default MCP tool surface from the full alpha catalog to a smaller
`core` profile. This is an intentional breaking default-behavior change before 1.0: common
bring-up, crash evidence, peripheral inspection, RTOS inspection, logging, build, flash, and verify
flows remain available by default, while expert/debugger-control tools require explicit opt-in.

## Highlights

- Default startup now exposes the fixed `core` tool set.
- Set `MCUBUDDY_TOOL_PROFILE=full` to expose the complete legacy tool catalog.
- Added structured evidence entry points:
  `collect_crash_evidence`, `collect_startup_evidence`, `collect_peripheral_evidence`, and
  `collect_rtos_evidence`.
- `list_tool_safety(include_hidden=false)` now reports `active_profile` and only lists visible
  tools by default. Use `include_hidden=true` to inspect metadata for the full catalog without
  changing the current MCP session.

## Migration

For an existing MCP config that needs the old full catalog:

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

`full` is not deprecated; it is the expert profile. Restart the MCP server after changing the
profile, and disconnect probes or log channels before restarting if a board is attached.
