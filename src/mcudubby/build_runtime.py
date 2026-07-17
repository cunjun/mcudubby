from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .config import BuildConfig, ElfConfig
from .errors import ConfigurationError


class KeilBuildRuntime:
    """Minimal Keil UV4 batch build/flash runtime for Windows."""

    def build(
        self,
        build: BuildConfig,
        elf: ElfConfig,
        timeout_seconds: int = 120,
    ) -> dict[str, Any]:
        uv4_path = self._require_path(build.uv4_path, "build.uv4_path")
        project_path = self._require_path(build.project_path, "build.project_path")
        target_name = self._require_value(build.target_name, "build.target_name")
        log_path = self._resolve_log_path(build.build_log_path, project_path, "mcudubby_build.log")

        command = [
            str(uv4_path),
            "-b",
            str(project_path),
            "-t",
            target_name,
            "-j0",
            "-o",
            str(log_path),
        ]
        log_path.unlink(missing_ok=True)
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
        log_text = self._read_text_if_exists(log_path)
        firmware = self._collect_firmware_info(elf.path)

        build_ok = self._build_succeeded(completed.returncode, log_text)
        return {
            "status": "ok" if build_ok else "error",
            "summary": self._summarize_build(completed.returncode, log_text),
            "command": command,
            "returncode": completed.returncode,
            "build_log_path": str(log_path),
            "build_log": log_text,
            "firmware": firmware,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }

    def flash(
        self,
        build: BuildConfig,
        elf: ElfConfig,
        timeout_seconds: int = 120,
    ) -> dict[str, Any]:
        uv4_path = self._require_path(build.uv4_path, "build.uv4_path")
        project_path = self._require_path(build.project_path, "build.project_path")
        target_name = self._require_value(build.target_name, "build.target_name")
        log_path = self._resolve_log_path(build.flash_log_path, project_path, "mcudubby_flash.log")

        command = [
            str(uv4_path),
            "-f",
            str(project_path),
            "-t",
            target_name,
            "-o",
            str(log_path),
        ]
        log_path.unlink(missing_ok=True)
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
        log_text = self._read_text_if_exists(log_path)
        firmware = self._collect_firmware_info(elf.path)

        flash_ok = self._flash_succeeded(completed.returncode, log_text)
        return {
            "status": "ok" if flash_ok else "error",
            "summary": self._summarize_flash(completed.returncode, log_text),
            "command": command,
            "returncode": completed.returncode,
            "flash_log_path": str(log_path),
            "flash_log": log_text,
            "firmware": firmware,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }

    @staticmethod
    def _require_value(value: str | None, field_name: str) -> str:
        if not value:
            raise ConfigurationError(f"Missing required runtime configuration: {field_name}")
        return value

    def _require_path(self, value: str | None, field_name: str) -> Path:
        path = Path(self._require_value(value, field_name))
        if not path.exists():
            raise ConfigurationError(f"Configured path does not exist for {field_name}: {path}")
        return path

    @staticmethod
    def _resolve_log_path(configured: str | None, project_path: Path, fallback_name: str) -> Path:
        if configured:
            log_path = Path(configured)
        else:
            project_dir = project_path.parent
            for candidate_dir in (
                project_dir / "Objects",
                project_dir / "OBJ",
                project_dir / "Output",
            ):
                if candidate_dir.exists():
                    log_path = candidate_dir / fallback_name
                    break
            else:
                log_path = project_dir / fallback_name
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return log_path

    @staticmethod
    def _read_text_if_exists(path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _build_succeeded(returncode: int, log_text: str) -> bool:
        return returncode == 0 and "0 Error(s)" in log_text

    @staticmethod
    def _flash_succeeded(returncode: int, log_text: str) -> bool:
        return returncode == 0 and "Verify OK" in log_text and "Application running" in log_text

    @staticmethod
    def _summarize_build(returncode: int, log_text: str) -> str:
        if KeilBuildRuntime._build_succeeded(returncode, log_text):
            return "Keil batch build completed successfully."
        if not log_text:
            return f"Keil batch build finished with return code {returncode}, but no build log was captured."
        return "Keil batch build reported errors."

    @staticmethod
    def _summarize_flash(returncode: int, log_text: str) -> str:
        if KeilBuildRuntime._flash_succeeded(returncode, log_text):
            return "Keil batch flash download completed successfully."
        if not log_text:
            return f"Keil batch flash finished with return code {returncode}, but no flash log was captured."
        return "Keil batch flash download reported errors."

    @staticmethod
    def _collect_firmware_info(elf_path: str | None) -> dict[str, Any] | None:
        if not elf_path:
            return None
        axf_path = Path(elf_path)
        if not axf_path.exists():
            return {"path": str(axf_path), "exists": False}

        hex_path = axf_path.with_suffix(".hex")
        return {
            "path": str(axf_path),
            "exists": True,
            "size_bytes": axf_path.stat().st_size,
            "last_modified": axf_path.stat().st_mtime,
            "hex_path": str(hex_path),
            "hex_exists": hex_path.exists(),
        }
