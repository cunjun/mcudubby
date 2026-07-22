from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import RuntimeConfig


def runtime_config_for(session: object) -> RuntimeConfig:
    config = getattr(session, "config", None)
    return config if isinstance(config, RuntimeConfig) else RuntimeConfig()


def blocked(summary: str, *, guard: str, details: dict[str, Any] | None = None) -> dict:
    return {
        "status": "error",
        "summary": summary,
        "security": {
            "guard": guard,
            "blocked": True,
            "details": details or {},
        },
    }


def ensure_memory_read_allowed(config: RuntimeConfig, size: int) -> dict | None:
    if size < 0:
        return blocked("Memory read size must not be negative.", guard="memory.max_read_size")
    max_size = config.memory.max_read_size
    if size > max_size:
        return blocked(
            f"Memory read of {size} byte(s) exceeds configured limit of {max_size}.",
            guard="memory.max_read_size",
            details={"requested_size": size, "max_read_size": max_size},
        )
    return None


def ensure_memory_write_allowed(config: RuntimeConfig, size: int) -> dict | None:
    if not config.memory.allow_write:
        return blocked(
            "Memory writes are disabled by configuration.",
            guard="memory.allow_write",
            details={"allow_write": False},
        )
    max_size = config.memory.max_write_size
    if size > max_size:
        return blocked(
            f"Memory write of {size} byte(s) exceeds configured limit of {max_size}.",
            guard="memory.max_write_size",
            details={"requested_size": size, "max_write_size": max_size},
        )
    return None


def ensure_rtt_scan_allowed(config: RuntimeConfig, size: int) -> dict | None:
    if size < 0:
        return blocked(
            "RTT scan size must not be negative.",
            guard="security.max_rtt_scan_size",
        )
    max_size = config.security.max_rtt_scan_size
    if size > max_size:
        return blocked(
            f"RTT scan of {size} byte(s) exceeds configured limit of {max_size}.",
            guard="security.max_rtt_scan_size",
            details={"requested_size": size, "max_rtt_scan_size": max_size},
        )
    return None


def ensure_flash_erase_allowed(config: RuntimeConfig) -> dict | None:
    if config.flash.allow_erase:
        return None
    return blocked(
        "Flash erase is disabled by configuration.",
        guard="flash.allow_erase",
        details={"allow_erase": False},
    )


def ensure_flash_program_allowed(config: RuntimeConfig, size: int) -> dict | None:
    if not config.flash.allow_program:
        return blocked(
            "Flash programming is disabled by configuration.",
            guard="flash.allow_program",
            details={"allow_program": False},
        )
    return ensure_flash_payload_size_allowed(config, size)


def ensure_flash_payload_size_allowed(config: RuntimeConfig, size: int) -> dict | None:
    max_size = config.flash.max_binary_size
    if size > max_size:
        return blocked(
            f"Flash payload of {size} byte(s) exceeds configured limit of {max_size}.",
            guard="flash.max_binary_size",
            details={"requested_size": size, "max_binary_size": max_size},
        )
    return None


def ensure_file_allowed(config: RuntimeConfig, path: str | Path) -> dict | None:
    allowed_roots = config.security.allowed_file_paths
    if not allowed_roots:
        return None

    try:
        candidate = Path(path).expanduser().resolve(strict=False)
    except OSError as exc:
        return blocked(
            f"Could not resolve path '{path}': {exc}",
            guard="security.allowed_file_paths",
        )

    for root in allowed_roots:
        try:
            resolved_root = Path(root).expanduser().resolve(strict=False)
        except OSError:
            continue
        if candidate == resolved_root or resolved_root in candidate.parents:
            return None

    return blocked(
        f"Path '{candidate}' is outside configured allowed_file_paths.",
        guard="security.allowed_file_paths",
        details={"path": str(candidate), "allowed_file_paths": allowed_roots},
    )


def ensure_file_size_allowed(config: RuntimeConfig, path: str | Path) -> dict | None:
    try:
        size = Path(path).stat().st_size
    except OSError as exc:
        return blocked(f"Could not stat file '{path}': {exc}", guard="flash.max_binary_size")
    return ensure_flash_program_allowed(config, size)
