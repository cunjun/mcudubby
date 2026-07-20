from __future__ import annotations

from copy import deepcopy
from typing import Any

from .chip_matcher import match_chip_name, normalize_backend_name


_PATCH_TABLE = {
    "jlink": {
        "STM32F103C8": {
            "support_tier": "validated",
            "recommended_probe": "J-Link",
            "validated_hardware": [
                {
                    "board": "Custom",
                    "mcu": "STM32F103C8",
                    "probe": "J-Link",
                    "notes": "Validated with native RTT, flash, source-level debugging, and J-Link GDB server.",
                }
            ],
            "validated_capabilities": [
                "connect",
                "halt",
                "reset",
                "memory",
                "registers",
                "flash",
                "watchpoints",
                "gdb_server",
                "rtt",
                "source_debug",
            ],
            "connect_hints": {
                "speeds": [4000, 1000, 400, "auto"],
            },
            "post_connect_checks": {
                "read_state": True,
            },
            "notes": [
                "Prefer SWD-only bring-up on STM32F103C8 boards when trace pins are shared.",
            ],
            "warnings": [
                "PB3 may be shared with TRACESWO, GPIO, or SPI functions on small F103 boards.",
            ],
            "recovery_guidance": [
                "If attach fails, retry with lower SWD speed before changing firmware.",
                "If the target still fails to respond, try under-reset attach from a pyOCD backend or external tool.",
            ],
        },
        "STM32L496VETx": {
            "support_tier": "validated",
            "recommended_probe": "J-Link",
            "validated_hardware": [
                {
                    "board": "ATK_PICTURE",
                    "mcu": "STM32L496VETx",
                    "probe": "J-Link",
                    "notes": "Alias/patch path validated; primary hardware validation remains on ST-Link/pyOCD.",
                }
            ],
            "validated_capabilities": [
                "connect",
                "halt",
                "reset",
                "memory",
                "registers",
            ],
            "connect_hints": {
                "speeds": [4000, 1000, "auto"],
            },
            "post_connect_checks": {
                "read_state": True,
            },
            "notes": [
                "L4 boards usually tolerate 4 MHz SWD; fall back to 1 MHz before auto.",
            ],
            "warnings": [],
            "recovery_guidance": [
                "If attach is unstable, retry at 1 MHz before switching probes.",
            ],
        },
    },
    "pyocd": {
        "py32f030x8": {
            "support_tier": "validated",
            "recommended_probe": "CMSIS-DAP",
            "validated_hardware": [
                {
                    "board": "S020A0",
                    "mcu": "PY32F030X8",
                    "probe": "jixin.pro CMSIS-DAP_LU",
                    "notes": (
                        "Validated with pyOCD, Puya.PY32F0xx_DFP.1.2.8.pack, "
                        "read-only smoke test, vector-table read, and AXF symbol context."
                    ),
                }
            ],
            "validated_capabilities": [
                "connect",
                "halt",
                "resume",
                "memory",
                "registers",
                "vector_table",
                "source_debug",
            ],
            "connect_hints": {
                "attempts": [
                    {"frequency": 100000, "connect_mode": "attach"},
                    {"frequency": 100000, "connect_mode": "under-reset"},
                ],
            },
            "post_connect_checks": {
                "read_state": True,
            },
            "notes": [
                "pyOCD needs the Puya PY32F0xx CMSIS-Pack for this target.",
                "McuBuddy auto-discovers Puya.PY32F0xx_DFP.*.pack from a local packs/ directory when present.",
            ],
            "warnings": [
                "If attach is unstable, keep SWD at 100 kHz before trying faster clocks.",
            ],
            "recovery_guidance": [
                "Use attach first so running firmware is minimally disturbed.",
                "If attach fails, retry under-reset at 100 kHz with the same CMSIS-Pack.",
            ],
        },
        "stm32f103c8": {
            "support_tier": "known",
            "recommended_probe": "CMSIS-DAP or ST-Link",
            "validated_hardware": [
                {
                    "board": "Custom",
                    "mcu": "STM32F103C8",
                    "probe": "J-Link",
                    "notes": "pyOCD attach strategy validated in unit coverage; real hardware validation focused on J-Link for this board.",
                }
            ],
            "validated_capabilities": [
                "connect_fallback",
                "target_alias",
            ],
            "connect_hints": {
                "attempts": [
                    {"frequency": 4000000, "connect_mode": "attach"},
                    {"frequency": 1000000, "connect_mode": "attach"},
                    {"frequency": 1000000, "connect_mode": "under-reset"},
                ],
            },
            "post_connect_checks": {
                "read_state": True,
            },
            "notes": [
                "Use under-reset fallback for STM32F103C8 boards that fail normal attach.",
            ],
            "warnings": [
                "Small F103 boards may expose fewer recovery options when SWD pins are repurposed by the application.",
            ],
            "recovery_guidance": [
                "Prefer attach first, then under-reset at 1 MHz if the core is not responsive.",
            ],
        },
        "stm32l496vetx": {
            "support_tier": "validated",
            "recommended_probe": "ST-Link",
            "validated_hardware": [
                {
                    "board": "ATK_PICTURE",
                    "mcu": "STM32L496VETx",
                    "probe": "ST-Link",
                    "notes": "Primary full-stack validation board for McuBuddy.",
                }
            ],
            "validated_capabilities": [
                "connect",
                "halt",
                "reset",
                "memory",
                "registers",
                "flash",
                "rtt",
                "rtos",
                "diagnose",
                "gdb_server",
                "source_debug",
            ],
            "connect_hints": {
                "attempts": [
                    {"frequency": 4000000, "connect_mode": "attach"},
                    {"frequency": 1000000, "connect_mode": "attach"},
                ],
            },
            "post_connect_checks": {
                "read_state": True,
            },
            "notes": [
                "STM32L496 boards normally attach cleanly; keep under-reset as a manual fallback.",
            ],
            "warnings": [],
            "recovery_guidance": [
                "Use under-reset manually only if normal attach fails after lowering frequency.",
            ],
        },
    },
}


def resolve_device_patch(target: str, backend: str = "pyocd") -> dict[str, Any]:
    canonical_backend = normalize_backend_name(backend)
    if canonical_backend is None:
        return {
            "status": "error",
            "summary": f"Unsupported probe backend '{backend}'.",
            "backend": backend,
            "input": target,
            "supported_backends": sorted(_PATCH_TABLE.keys()),
        }

    match_result = match_chip_name(target, backend=canonical_backend)
    if match_result["status"] != "ok":
        return match_result
    matched_target = match_result["matched_target"]
    patch = _PATCH_TABLE.get(canonical_backend, {}).get(matched_target)
    if patch is None:
        return {
            "status": "ok",
            "summary": f"No device patch registered for {matched_target} on {canonical_backend}.",
            "backend": canonical_backend,
            "input": target,
            "matched_target": matched_target,
            "match_result": match_result,
            "patch_applied": False,
            "support_tier": "unknown",
            "recommended_probe": None,
            "validated_hardware": [],
            "validated_capabilities": [],
            "connect_hints": {},
            "post_connect_checks": {},
            "notes": [],
            "warnings": [],
            "recovery_guidance": [],
        }

    return {
        "status": "ok",
        "summary": f"Resolved device patch for {matched_target} on {canonical_backend}.",
        "backend": canonical_backend,
        "input": target,
        "matched_target": matched_target,
        "match_result": match_result,
        "patch_applied": True,
        "support_tier": patch.get("support_tier", "known"),
        "recommended_probe": patch.get("recommended_probe"),
        "validated_hardware": deepcopy(patch.get("validated_hardware", [])),
        "validated_capabilities": deepcopy(patch.get("validated_capabilities", [])),
        "connect_hints": deepcopy(patch.get("connect_hints", {})),
        "post_connect_checks": deepcopy(patch.get("post_connect_checks", {})),
        "notes": deepcopy(patch.get("notes", [])),
        "warnings": deepcopy(patch.get("warnings", [])),
        "recovery_guidance": deepcopy(patch.get("recovery_guidance", [])),
    }


def list_supported_targets(backend: str | None = None) -> dict[str, Any]:
    if backend is not None:
        canonical_backend = normalize_backend_name(backend)
        if canonical_backend is None:
            return {
                "status": "error",
                "summary": f"Unsupported probe backend '{backend}'.",
                "backend": backend,
                "supported_backends": sorted(_PATCH_TABLE.keys()),
            }
        backends = [canonical_backend]
    else:
        backends = sorted(_PATCH_TABLE.keys())
    targets: list[dict[str, Any]] = []

    for backend_name in backends:
        for target_name, patch in sorted(_PATCH_TABLE.get(backend_name, {}).items()):
            targets.append(
                {
                    "backend": backend_name,
                    "target": target_name,
                    "support_tier": patch.get("support_tier", "known"),
                    "recommended_probe": patch.get("recommended_probe"),
                    "validated_capabilities": deepcopy(patch.get("validated_capabilities", [])),
                    "validated_hardware": deepcopy(patch.get("validated_hardware", [])),
                }
            )

    return {
        "status": "ok",
        "summary": f"Found {len(targets)} supported target profile(s).",
        "backend": backends[0] if len(backends) == 1 else None,
        "targets": targets,
    }
