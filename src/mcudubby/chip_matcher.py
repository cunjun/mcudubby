from __future__ import annotations

from copy import deepcopy
from typing import Any


_ALIAS_TABLE = {
    "pyocd": {
        "py32f030x8": "py32f030x8",
        "stm32f103c8": "stm32f103c8",
        "stm32f103c8t6": "stm32f103c8",
        "stm32f103ze": "stm32f103ze",
        "stm32f103zet6": "stm32f103ze",
        "stm32l496ve": "stm32l496vetx",
        "stm32l496vetx": "stm32l496vetx",
    },
    "jlink": {
        "stm32f103c8": "STM32F103C8",
        "stm32f103c8t6": "STM32F103C8",
        "stm32f103ze": "STM32F103ZE",
        "stm32f103zet6": "STM32F103ZE",
        "stm32l496ve": "STM32L496VETx",
        "stm32l496vetx": "STM32L496VETx",
    },
}

_BACKEND_ALIASES = {
    "pyocd": "pyocd",
    "stlink": "pyocd",
    "st-link": "pyocd",
    "cmsisdap": "pyocd",
    "cmsis-dap": "pyocd",
    "jlink": "jlink",
    "j-link": "jlink",
}


def _normalize_chip_name(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch.isalnum())


def normalize_backend_name(backend: str) -> str | None:
    normalized = backend.strip().lower()
    return _BACKEND_ALIASES.get(normalized)


def match_chip_name(name: str, backend: str = "pyocd") -> dict[str, Any]:
    """Resolve common MCU aliases to a backend-specific target name."""
    canonical_backend = normalize_backend_name(backend)
    if canonical_backend is None:
        return {
            "status": "error",
            "summary": f"Unsupported probe backend '{backend}'.",
            "input": name,
            "backend": backend,
            "supported_backends": sorted(set(_BACKEND_ALIASES.values())),
        }

    normalized = _normalize_chip_name(name)
    aliases = deepcopy(_ALIAS_TABLE.get(canonical_backend, {}))
    matched = aliases.get(normalized)
    if matched is not None:
        return {
            "status": "ok",
            "summary": f"Matched '{name}' to {matched} for {canonical_backend}.",
            "input": name,
            "backend": canonical_backend,
            "normalized_input": normalized,
            "matched_target": matched,
            "confidence": "high",
        }

    return {
        "status": "ok",
        "summary": f"No alias match for '{name}'; using the original target name.",
        "input": name,
        "backend": canonical_backend,
        "normalized_input": normalized,
        "matched_target": name,
        "confidence": "pass_through",
    }
