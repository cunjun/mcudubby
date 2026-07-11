# mcudubby v0.4.0

Initial public release of `mcudubby`, an MCP server for AI-assisted MCU debugging and real-board firmware diagnosis.

## What's Included

- MCP server entrypoint: `python -m mcudubby`
- Probe control workflows for halt, resume, reset, stepping, breakpoints, watchpoints, registers, memory, and flash operations
- pyOCD support for ST-Link and CMSIS-DAP probes
- J-Link support through `pylink-square`
- ELF/DWARF source context, symbol lookup, stack inspection, disassembly, and source navigation helpers
- UART, Segger RTT, SVD peripheral register, FreeRTOS, and GDB server tooling
- AI-oriented diagnosis flows for startup failures, HardFaults, stack overflow, peripheral issues, clock issues, and debug loops
- English and Chinese documentation, quickstarts, support matrix, and bundled `mcubug` assistant skill references

## Install

```bash
pip install mcudubby
```

From this release, you can also download the attached wheel or source distribution:

- `mcudubby-0.4.0-py3-none-any.whl`
- `mcudubby-0.4.0.tar.gz`

## Notes

This is the first public baseline. Hardware-facing workflows depend on local probe drivers, board wiring, target firmware symbols, and optional backend packages such as `pylink-square`.
