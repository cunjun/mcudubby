from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
from typing import Any, Literal

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from pydantic import BaseModel, Field, ValidationError, field_validator


class ServerConfig(BaseModel):
    tool_profile: Literal["core", "full"] = "core"


class ConnectAttempt(BaseModel):
    frequency: int | float | str
    connect_mode: Literal["halt", "pre-reset", "under-reset", "attach"] = "attach"


class ProbeConfig(BaseModel):
    backend: str = "pyocd"
    target: str | None = None
    unique_id: str | None = None
    jlink_dll_path: str | None = None
    probe_rs_sidecar_path: str | None = None
    pack_paths: list[str] = Field(default_factory=list)
    connect_attempts: list[ConnectAttempt] = Field(default_factory=list)


def connect_attempts_to_dicts(
    attempts: list[ConnectAttempt] | list[Mapping[str, object]],
) -> list[dict[str, object]]:
    return [
        attempt.model_dump() if isinstance(attempt, ConnectAttempt) else dict(attempt)
        for attempt in attempts
    ]


class LogConfig(BaseModel):
    backend: str = "uart"
    port: str | None = None
    baudrate: int = 115200


class ElfConfig(BaseModel):
    path: str | None = None


class BuildConfig(BaseModel):
    backend: str = "keil_uv4"
    uv4_path: str | None = None
    project_path: str | None = None
    target_name: str | None = None
    build_log_path: str | None = None
    flash_log_path: str | None = None


class MemoryConfig(BaseModel):
    max_read_size: int = 4096
    max_write_size: int = 1024
    allow_write: bool = False

    @field_validator("max_read_size", "max_write_size")
    @classmethod
    def _positive_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return value


class FlashConfig(BaseModel):
    allow_erase: bool = False
    allow_program: bool = True
    max_binary_size: int = 16 * 1024 * 1024
    verify_after_program: bool = True

    @field_validator("max_binary_size")
    @classmethod
    def _positive_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return value


class SecurityConfig(BaseModel):
    allowed_file_paths: list[str] = Field(default_factory=list)
    max_rtt_scan_size: int = 0x50000

    @field_validator("max_rtt_scan_size")
    @classmethod
    def _positive_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return value


class DemoProfile(BaseModel):
    name: str
    description: str
    probe: ProbeConfig
    log: LogConfig
    elf: ElfConfig
    build: BuildConfig = Field(default_factory=BuildConfig)
    suspected_stage: str | None = None


class RuntimeConfig(BaseModel):
    active_profile: str | None = None
    server: ServerConfig = Field(default_factory=ServerConfig)
    probe: ProbeConfig = Field(default_factory=ProbeConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    elf: ElfConfig = Field(default_factory=ElfConfig)
    build: BuildConfig = Field(default_factory=BuildConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    flash: FlashConfig = Field(default_factory=FlashConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    suspected_stage: str | None = None

    def apply_profile(self, profile: DemoProfile) -> None:
        self.active_profile = profile.name
        self.probe = profile.probe.model_copy(deep=True)
        self.log = profile.log.model_copy(deep=True)
        self.elf = profile.elf.model_copy(deep=True)
        self.build = profile.build.model_copy(deep=True)
        self.suspected_stage = profile.suspected_stage


def default_config() -> RuntimeConfig:
    return RuntimeConfig()


def load_config_file(path: str | Path) -> RuntimeConfig:
    config_path = Path(path)
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    return RuntimeConfig.model_validate(data)


def load_config(
    path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, object] | None = None,
) -> RuntimeConfig:
    config = load_config_file(path) if path else default_config()
    config = apply_environment_overrides(config, environ=environ)
    return apply_config_overrides(config, cli_overrides)


_ENVIRONMENT_OVERRIDE_PATHS = {
    "MCUBUDDY_TOOL_PROFILE": "server.tool_profile",
    "MCUBUDDY_PROBE_BACKEND": "probe.backend",
    "MCUBUDDY_PROBE_TARGET": "probe.target",
    "MCUBUDDY_MAX_READ_SIZE": "memory.max_read_size",
    "MCUBUDDY_MAX_WRITE_SIZE": "memory.max_write_size",
    "MCUBUDDY_ALLOW_MEMORY_WRITE": "memory.allow_write",
    "MCUBUDDY_ALLOW_FLASH_ERASE": "flash.allow_erase",
    "MCUBUDDY_ALLOW_FLASH_PROGRAM": "flash.allow_program",
    "MCUBUDDY_MAX_BINARY_SIZE": "flash.max_binary_size",
    "MCUBUDDY_MAX_RTT_SCAN_SIZE": "security.max_rtt_scan_size",
}


def apply_environment_overrides(
    config: RuntimeConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    source = os.environ if environ is None else environ
    assignments = []
    for name, path in _ENVIRONMENT_OVERRIDE_PATHS.items():
        value = source.get(name)
        if value in (None, ""):
            continue
        normalized = value.strip().lower() if name == "MCUBUDDY_TOOL_PROFILE" else value
        assignments.append(f"{path}={normalized}")
    return apply_config_overrides(config, parse_cli_overrides(assignments))


def parse_cli_overrides(assignments: list[str] | None) -> dict[str, object]:
    overrides: dict[str, object] = {}
    for assignment in assignments or []:
        path, separator, raw_value = assignment.partition("=")
        parts = path.strip().split(".")
        if not separator or len(parts) != 2 or not all(parts):
            raise ValueError(
                f"Invalid config override {assignment!r}; expected SECTION.FIELD=VALUE."
            )
        section, field = parts
        section_info = RuntimeConfig.model_fields.get(section)
        section_model = section_info.annotation if section_info else None
        if (
            section_info is None
            or not isinstance(section_model, type)
            or not issubclass(section_model, BaseModel)
            or field not in section_model.model_fields
        ):
            raise ValueError(f"Unknown config override {section}.{field}.")
        section_values = overrides.setdefault(section, {})
        if not isinstance(section_values, dict):
            raise ValueError(f"Config override section {section!r} is invalid.")
        section_values[field] = _parse_override_value(raw_value.strip())
    return overrides


def apply_config_overrides(
    config: RuntimeConfig,
    overrides: Mapping[str, object] | None,
) -> RuntimeConfig:
    if not overrides:
        return config
    data = config.model_dump()
    _merge_config_values(data, overrides)
    return RuntimeConfig.model_validate(data)


def _merge_config_values(target: dict[str, Any], values: Mapping[str, object]) -> None:
    for key, value in values.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _merge_config_values(target[key], value)
        else:
            target[key] = value


def _parse_override_value(value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def validate_config_file(path: str | Path) -> tuple[RuntimeConfig | None, list[dict[str, object]]]:
    try:
        return load_config_file(path), []
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return None, [{"loc": ("file",), "msg": str(exc), "type": exc.__class__.__name__}]
    except ValidationError as exc:
        return None, list(exc.errors())


def config_to_toml(config: RuntimeConfig | None = None) -> str:
    data = (config or default_config()).model_dump()
    sections = [
        "server",
        "probe",
        "log",
        "elf",
        "build",
        "memory",
        "flash",
        "security",
    ]
    lines: list[str] = [
        "# McuBuddy runtime configuration",
        "# Save as mcubuddy.toml and pass --config <path> to CLI commands.",
        "",
    ]
    for section in sections:
        values = data[section]
        lines.append(f"[{section}]")
        for key, value in values.items():
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if value is None:
        return '""'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def config_for_display(config: RuntimeConfig) -> dict[str, object]:
    data = config.model_dump()
    probe = data.get("probe")
    if isinstance(probe, dict):
        for key in ("jlink_dll_path", "probe_rs_sidecar_path"):
            if probe.get(key):
                probe[key] = "<configured>"
    return data


def _local_pack_paths(pattern: str) -> list[str]:
    packs_dir = Path(__file__).resolve().parents[2] / "packs"
    if not packs_dir.is_dir():
        return []
    return [str(path.resolve()) for path in sorted(packs_dir.glob(pattern))]


def get_builtin_profiles() -> dict[str, DemoProfile]:
    return {
        "stm32l4_atk_led_demo": DemoProfile(
            name="stm32l4_atk_led_demo",
            description=(
                "STM32L496VETx startup-failure demo. "
                "Uses pyOCD + ST-Link, UART at 115200, and a Keil UV4 project. "
                "Override paths to match your local setup before use."
            ),
            probe=ProbeConfig(
                backend="pyocd",
                target="stm32l496vetx",
            ),
            log=LogConfig(
                backend="uart",
                port="COM3",  # override with your actual COM port
                baudrate=115200,
            ),
            elf=ElfConfig(
                path=None,  # set to your .axf/.elf path, e.g. "C:/project/OBJ/firmware.axf"
            ),
            build=BuildConfig(
                backend="keil_uv4",
                uv4_path=None,  # e.g. "C:/Keil_v5/UV4/UV4.exe"
                project_path=None,  # e.g. "C:/project/USER/firmware.uvprojx"
                target_name=None,  # Keil target name as shown in the project
            ),
            suspected_stage="sensor init",
        ),
        "py32f030x8_cmsis_dap": DemoProfile(
            name="py32f030x8_cmsis_dap",
            description=(
                "PY32F030X8 bring-up profile for pyOCD + CMSIS-DAP. "
                "Uses conservative 100 kHz SWD attach and auto-picks a local Puya PY32F0xx pack "
                "from packs/ when available."
            ),
            probe=ProbeConfig(
                backend="pyocd",
                target="py32f030x8",
                pack_paths=_local_pack_paths("Puya.PY32F0xx_DFP.*.pack"),
                connect_attempts=[
                    ConnectAttempt(frequency=100000, connect_mode="attach"),
                    ConnectAttempt(frequency=100000, connect_mode="under-reset"),
                ],
            ),
            log=LogConfig(
                backend="uart",
                port=None,
                baudrate=115200,
            ),
            elf=ElfConfig(path=None),
        ),
    }
