from __future__ import annotations

from pathlib import Path
from typing import Literal

from ...backends.probe.base import ProbeCapability, probe_supports
from ...session import SessionState
from ...security_guards import (
    ensure_flash_erase_allowed,
    ensure_flash_payload_size_allowed,
    ensure_flash_program_allowed,
    ensure_file_allowed,
    ensure_file_size_allowed,
    runtime_config_for,
)
from ...tool_safety import require_tool_confirmation


def erase_flash(
    session: SessionState,
    start_address: int | None = None,
    end_address: int | None = None,
    chip_erase: bool = False,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("erase_flash", confirm):
        return blocked
    if blocked := ensure_flash_erase_allowed(runtime_config_for(session)):
        return blocked
    try:
        return session.probe.erase_flash(
            start_address=start_address,
            end_address=end_address,
            chip_erase=chip_erase,
        )
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }


def program_flash(
    session: SessionState,
    address: int,
    data: list[int] | bytes,
    verify: bool = True,
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("program_flash", confirm):
        return blocked
    try:
        payload = bytes(data) if not isinstance(data, bytes) else data
        if blocked := ensure_flash_program_allowed(runtime_config_for(session), len(payload)):
            return blocked
        return session.probe.program_flash(address=address, data=payload, verify=verify)
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }


def flash_image(
    session: SessionState,
    path: str,
    address: int,
    erase_mode: Literal["sector", "chip"] = "sector",
    verify: bool = True,
    reset_after: bool = True,
    confirm: bool = False,
) -> dict:
    """Safely flash a raw binary file through one erase/program transaction."""
    if blocked := require_tool_confirmation("flash_image", confirm):
        return blocked

    config = runtime_config_for(session)
    if blocked := ensure_flash_erase_allowed(config):
        return blocked
    if not probe_supports(session.probe, ProbeCapability.FLASH_IMAGE):
        return {
            "status": "error",
            "summary": "The configured probe backend does not support transactional image flashing.",
            "required_capability": ProbeCapability.FLASH_IMAGE.value,
            "backend": config.probe.backend,
        }
    if blocked := ensure_file_allowed(config, path):
        return blocked

    try:
        image_path = Path(path).expanduser().resolve(strict=True)
        if not image_path.is_file():
            raise ValueError(f"Firmware path is not a file: {image_path}")
        if blocked := ensure_file_allowed(config, image_path):
            return blocked
        if blocked := ensure_file_size_allowed(config, image_path):
            return blocked
        payload = image_path.read_bytes()
        if not payload:
            raise ValueError("Firmware image must not be empty.")

        result = session.probe.flash_image(
            address=address,
            data=payload,
            erase_mode=erase_mode,
            verify=verify,
            reset_after=reset_after,
        )
        return {
            **result,
            "path": str(image_path),
            "size": len(payload),
        }
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }


def verify_flash(
    session: SessionState,
    address: int,
    data: list[int] | bytes,
) -> dict:
    try:
        payload = bytes(data) if not isinstance(data, bytes) else data
        if blocked := ensure_flash_payload_size_allowed(runtime_config_for(session), len(payload)):
            return blocked
        return session.probe.verify_flash(address=address, data=payload)
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }
