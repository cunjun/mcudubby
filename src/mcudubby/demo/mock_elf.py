from __future__ import annotations


class MockElfManager:
    def __init__(self) -> None:
        self._loaded = False

    def load(self, path: str) -> dict:
        self._loaded = True
        return {
            "status": "ok",
            "summary": f"Loaded mock ELF symbols from {path}.",
            "symbol_count": 3,
        }

    def resolve_address(self, address: int) -> dict:
        mapping = {
            0x08001234: {
                "symbol": "HardFault_Handler",
                "source": {"file": "src/startup_stm32l4xx.s", "line": 121},
            },
            0x08004567: {"symbol": "sensor_init", "source": {"file": "src/sensor.c", "line": 84}},
        }
        result = mapping.get(address, {"symbol": None, "source": None})
        return {
            "address": hex(address),
            "symbol": result["symbol"],
            "source": result["source"],
        }

    def resolve_symbol(self, name: str) -> dict:
        mapping = {
            "HardFault_Handler": {
                "address": "0x8001234",
                "source": {"file": "src/startup_stm32l4xx.s", "line": 121},
            },
            "sensor_init": {"address": "0x8004567", "source": {"file": "src/sensor.c", "line": 84}},
        }
        result = mapping.get(name, {"address": None, "source": None})
        return {
            "symbol": name,
            "address": result["address"],
            "source": result["source"],
        }

    @property
    def is_loaded(self) -> bool:
        return self._loaded
