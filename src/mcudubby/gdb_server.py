from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


class GdbServerRuntime:
    """Manage pyOCD or J-Link GDB server subprocesses."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._log_handle = None
        self._log_path: str | None = None
        self._command: list[str] | None = None
        self._cwd: str | None = None
        self._host: str = "127.0.0.1"
        self._port: int = 3333
        self._telnet_port: int = 4444
        self._probe_server_port: int = 5555
        self._backend: str = "pyocd"
        self._target: str | None = None
        self._unique_id: str | None = None
        self._interface: str | None = None
        self._speed: int | None = None
        self._exe_path: str | None = None
        self._elf_path: str | None = None
        self._persist: bool = False
        self._last_exit_code: int | None = None

    def start(
        self,
        *,
        target: str,
        unique_id: str | None = None,
        port: int = 3333,
        telnet_port: int = 4444,
        probe_server_port: int = 5555,
        allow_remote: bool = False,
        persist: bool = False,
        elf_path: str | None = None,
        cwd: str | None = None,
        startup_timeout_seconds: float = 1.0,
    ) -> dict[str, Any]:
        if self.is_running():
            return {
                "status": "ok",
                "summary": f"GDB server is already running on {self._host}:{self._port}.",
                **self.status(),
            }

        self._close_log_handle()

        host = "0.0.0.0" if allow_remote else "127.0.0.1"
        workdir = (
            Path(cwd) if cwd else (Path(elf_path).resolve().parent if elf_path else Path.cwd())
        )
        log_path = Path(tempfile.gettempdir()) / f"McuBubby_gdbserver_{port}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("w", encoding="utf-8", errors="replace")

        command = [
            sys.executable,
            "-m",
            "pyocd",
            "gdbserver",
            "--no-config",
            "-t",
            target,
            "-p",
            str(port),
            "-T",
            str(telnet_port),
            "-R",
            str(probe_server_port),
        ]
        if unique_id:
            command.extend(["-u", unique_id])
        if elf_path:
            command.extend(["--elf", elf_path])
        if allow_remote:
            command.append("--allow-remote")
        if persist:
            command.append("--persist")

        process = subprocess.Popen(
            command,
            cwd=str(workdir),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        time.sleep(max(0.1, startup_timeout_seconds))

        if process.poll() is not None:
            exit_code = process.returncode
            log_handle.close()
            self._log_handle = None
            log_text = (
                log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
            )
            self._process = None
            self._log_path = str(log_path)
            self._command = command
            self._cwd = str(workdir)
            self._last_exit_code = exit_code
            return {
                "status": "error",
                "summary": f"GDB server exited during startup with code {exit_code}.",
                "running": False,
                "host": host,
                "port": port,
                "telnet_port": telnet_port,
                "probe_server_port": probe_server_port,
                "target": target,
                "unique_id": unique_id,
                "elf_path": elf_path,
                "persist": persist,
                "command": command,
                "cwd": str(workdir),
                "log_path": str(log_path),
                "log_tail": self._tail_text(log_text),
                "exit_code": exit_code,
            }

        self._process = process
        self._log_handle = log_handle
        self._log_path = str(log_path)
        self._command = command
        self._cwd = str(workdir)
        self._host = host
        self._port = port
        self._telnet_port = telnet_port
        self._probe_server_port = probe_server_port
        self._backend = "pyocd"
        self._target = target
        self._unique_id = unique_id
        self._interface = None
        self._speed = None
        self._exe_path = sys.executable
        self._elf_path = elf_path
        self._persist = persist
        self._last_exit_code = None
        return {
            "status": "ok",
            "summary": f"Started GDB server on {host}:{port}.",
            **self.status(),
        }

    def start_jlink(
        self,
        *,
        target: str,
        serial_no: str | None = None,
        port: int = 2331,
        interface: str = "swd",
        speed: int = 4000,
        exe_path: str,
        cwd: str | None = None,
        startup_timeout_seconds: float = 1.0,
    ) -> dict[str, Any]:
        if self.is_running():
            return {
                "status": "ok",
                "summary": f"GDB server is already running on {self._host}:{self._port}.",
                **self.status(),
            }

        self._close_log_handle()

        host = "127.0.0.1"
        workdir = Path(cwd) if cwd else Path(exe_path).resolve().parent
        log_path = Path(tempfile.gettempdir()) / f"McuBubby_jlink_gdbserver_{port}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("w", encoding="utf-8", errors="replace")

        command = [
            exe_path,
            "-device",
            target,
            "-if",
            interface.upper(),
            "-speed",
            str(speed),
            "-port",
            str(port),
            "-noir",
        ]
        if serial_no:
            command.extend(["-select", f"usb={serial_no}"])

        process = subprocess.Popen(
            command,
            cwd=str(workdir),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        time.sleep(max(0.1, startup_timeout_seconds))

        if process.poll() is not None:
            exit_code = process.returncode
            log_handle.close()
            self._log_handle = None
            log_text = (
                log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
            )
            self._process = None
            self._log_path = str(log_path)
            self._command = command
            self._cwd = str(workdir)
            self._last_exit_code = exit_code
            return {
                "status": "error",
                "summary": f"GDB server exited during startup with code {exit_code}.",
                "running": False,
                "host": host,
                "port": port,
                "target": target,
                "unique_id": serial_no,
                "interface": interface.upper(),
                "speed": speed,
                "backend": "jlink",
                "exe_path": exe_path,
                "command": command,
                "cwd": str(workdir),
                "log_path": str(log_path),
                "log_tail": self._tail_text(log_text),
                "exit_code": exit_code,
            }

        self._process = process
        self._log_handle = log_handle
        self._log_path = str(log_path)
        self._command = command
        self._cwd = str(workdir)
        self._host = host
        self._port = port
        self._telnet_port = 0
        self._probe_server_port = 0
        self._backend = "jlink"
        self._target = target
        self._unique_id = serial_no
        self._interface = interface.upper()
        self._speed = speed
        self._exe_path = exe_path
        self._elf_path = None
        self._persist = False
        self._last_exit_code = None
        return {
            "status": "ok",
            "summary": f"Started J-Link GDB server on {host}:{port}.",
            **self.status(),
        }

    def stop(self, timeout_seconds: float = 5.0) -> dict[str, Any]:
        if self._process is None:
            return {
                "status": "ok",
                "summary": "GDB server is not running.",
                **self.status(),
            }

        process = self._process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=max(0.1, timeout_seconds))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)

        exit_code = process.returncode
        self._last_exit_code = exit_code
        self._process = None
        self._close_log_handle()
        return {
            "status": "ok",
            "summary": f"Stopped GDB server on {self._host}:{self._port}.",
            **self.status(),
            "exit_code": exit_code,
        }

    def status(self) -> dict[str, Any]:
        running = self.is_running()
        return {
            "running": running,
            "state": "running" if running else "stopped",
            "backend": self._backend,
            "host": self._host,
            "port": self._port,
            "telnet_port": self._telnet_port,
            "probe_server_port": self._probe_server_port,
            "target": self._target,
            "unique_id": self._unique_id,
            "interface": self._interface,
            "speed": self._speed,
            "exe_path": self._exe_path,
            "elf_path": self._elf_path,
            "persist": self._persist,
            "command": self._command,
            "cwd": self._cwd,
            "log_path": self._log_path,
            "exit_code": None if running else self._last_exit_code,
        }

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @staticmethod
    def _tail_text(text: str, line_count: int = 20) -> list[str]:
        lines = [line for line in text.splitlines() if line.strip()]
        return lines[-line_count:]

    def _close_log_handle(self) -> None:
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None
