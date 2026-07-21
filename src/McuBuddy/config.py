from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
from typing import Literal
import tomllib

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


def load_config(path: str | Path | None = None) -> RuntimeConfig:
    config = load_config_file(path) if path else default_config()
    apply_environment_overrides(config)
    return config


def apply_environment_overrides(config: RuntimeConfig) -> RuntimeConfig:
    tool_profile = os.environ.get("MCUBUDDY_TOOL_PROFILE")
    if tool_profile:
        config.server = ServerConfig(tool_profile=tool_profile.strip().lower())
    return config


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
