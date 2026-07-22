from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


PROFILE_ENV_VAR = "MCUBUDDY_TOOL_PROFILE"
TOOL_PROFILE_CORE = "core"
TOOL_PROFILE_FULL = "full"
VALID_TOOL_PROFILES = frozenset({TOOL_PROFILE_CORE, TOOL_PROFILE_FULL})
ToolProfileName = Literal["core", "full"]


CORE_TOOL_NAMES = frozenset(
    {
        "doctor",
        "first_contact",
        "list_tool_safety",
        "list_validation_records",
        "pack_diagnose",
        "pack_install",
        "match_chip_name",
        "get_target_info",
        "list_connected_probes",
        "configure_probe",
        "configure_elf",
        "elf_load",
        "svd_load",
        "probe_connect",
        "disconnect_all",
        "probe_halt",
        "probe_resume",
        "probe_reset",
        "read_stopped_context",
        "backtrace",
        "collect_crash_evidence",
        "collect_startup_evidence",
        "collect_peripheral_evidence",
        "collect_rtos_evidence",
        "svd_read_peripheral",
        "list_rtos_tasks",
        "rtos_task_context",
        "read_rtt_log",
        "configure_log",
        "log_connect",
        "uart_send",
        "uart_read_bytes",
        "uart_exchange",
        "log_tail",
        "discover_keil_projects",
        "configure_keil_project",
        "build_project",
        "flash_firmware",
        "flash_image",
        "compare_elf_to_flash",
    }
)


@dataclass(frozen=True)
class ToolProfile:
    name: ToolProfileName
    enabled_tool_names: frozenset[str] | None

    def allows(self, tool_name: str) -> bool:
        return self.enabled_tool_names is None or tool_name in self.enabled_tool_names


class ToolProfileError(ValueError):
    """Raised when a startup tool profile value is invalid."""


def _normalize_profile(value: str) -> ToolProfileName:
    normalized = value.strip().lower()
    if normalized in VALID_TOOL_PROFILES:
        return normalized  # type: ignore[return-value]
    options = ", ".join(sorted(VALID_TOOL_PROFILES))
    raise ToolProfileError(
        f"Unknown McuBuddy tool profile {value!r}. Valid values are: {options}."
    )


def resolve_tool_profile(
    explicit: str | None = None,
    *,
    environ: dict[str, str] | None = None,
) -> ToolProfile:
    value = explicit
    if value is None:
        env = os.environ if environ is None else environ
        value = env.get(PROFILE_ENV_VAR, TOOL_PROFILE_CORE)
    name = _normalize_profile(value)
    enabled = None if name == TOOL_PROFILE_FULL else CORE_TOOL_NAMES
    return ToolProfile(name=name, enabled_tool_names=enabled)
