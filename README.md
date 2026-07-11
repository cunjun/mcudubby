# mcudubby

AI-native debugging and observability for embedded boards.

`mcudubby` is an MCP server for AI-assisted MCU debugging and real-board firmware diagnosis. It gives AI assistants structured access to debug probes, CPU registers, memory, ELF/DWARF symbols, UART/RTT logs, SVD peripheral registers, RTOS state, flash operations, and GDB server lifecycle tools.

## Install

```bash
pip install mcudubby
```

From source:

```bash
git clone https://github.com/cunjun/mcudubby
cd mcudubby
pip install -e .
```

## MCP Configuration

```json
{
  "mcpServers": {
    "mcudubby": {
      "command": "python",
      "args": ["-m", "mcudubby"]
    }
  }
}
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
```

See [README_CN.md](README_CN.md) and [docs/README.md](docs/README.md) for more documentation.

## License

MIT. See [LICENSE](LICENSE).
