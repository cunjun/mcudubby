from __future__ import annotations

from types import SimpleNamespace

from McuBuddy.gdb_server import GdbServerRuntime
import McuBuddy.tools.gdb_server as gdb_server_tools
from McuBuddy.tools.gdb_server import (
    get_gdb_server_status,
    get_jlink_gdb_server_status,
    start_gdb_server,
    start_jlink_gdb_server,
    stop_gdb_server,
    stop_jlink_gdb_server,
)


class _FakeProcess:
    def __init__(self, poll_result=None) -> None:
        self._poll_result = poll_result
        self.returncode = poll_result
        self.terminated = False
        self.killed = False
        self.wait_timeout = None

    def poll(self):
        return self._poll_result

    def terminate(self) -> None:
        self.terminated = True
        self._poll_result = 0
        self.returncode = 0

    def wait(self, timeout=None):
        self.wait_timeout = timeout
        self._poll_result = 0
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.killed = True
        self._poll_result = -9
        self.returncode = -9


def test_start_gdb_server_uses_session_defaults() -> None:
    calls: list[dict] = []
    session = SimpleNamespace(
        config=SimpleNamespace(
            probe=SimpleNamespace(target="stm32l496vetx", unique_id="1234"),
            elf=SimpleNamespace(path="D:/demo/firmware.axf"),
        ),
        gdb_server=SimpleNamespace(
            start=lambda **kwargs: calls.append(kwargs) or {"status": "ok", "summary": "started"},
        ),
    )

    result = start_gdb_server(session, port=3335, persist=True)

    assert result["status"] == "ok"
    assert calls == [
        {
            "target": "stm32l496vetx",
            "unique_id": "1234",
            "port": 3335,
            "telnet_port": 4444,
            "probe_server_port": 5555,
            "allow_remote": False,
            "persist": True,
            "elf_path": "D:/demo/firmware.axf",
            "cwd": "D:\\demo",
        }
    ]


def test_start_gdb_server_requires_target() -> None:
    session = SimpleNamespace(
        config=SimpleNamespace(
            probe=SimpleNamespace(target=None, unique_id=None),
            elf=SimpleNamespace(path=None),
        ),
        gdb_server=SimpleNamespace(),
    )

    result = start_gdb_server(session)

    assert result["status"] == "error"


def test_start_gdb_server_requires_explicit_confirmation_for_remote_binding() -> None:
    calls: list[dict] = []
    session = SimpleNamespace(
        config=SimpleNamespace(
            probe=SimpleNamespace(target="stm32l496vetx", unique_id=None),
            elf=SimpleNamespace(path=None),
        ),
        gdb_server=SimpleNamespace(
            start=lambda **kwargs: calls.append(kwargs) or {"status": "ok"},
        ),
    )

    result = start_gdb_server(session, allow_remote=True)

    assert result["status"] == "error"
    assert result["safety"]["requires_confirmation"] is True
    assert calls == []


def test_start_gdb_server_allows_confirmed_remote_binding() -> None:
    calls: list[dict] = []
    session = SimpleNamespace(
        config=SimpleNamespace(
            probe=SimpleNamespace(target="stm32l496vetx", unique_id=None),
            elf=SimpleNamespace(path=None),
        ),
        gdb_server=SimpleNamespace(
            start=lambda **kwargs: calls.append(kwargs) or {"status": "ok"},
        ),
    )

    result = start_gdb_server(session, allow_remote=True, confirm_remote=True)

    assert result["status"] == "ok"
    assert calls[0]["allow_remote"] is True


def test_status_and_stop_wrap_runtime() -> None:
    session = SimpleNamespace(
        gdb_server=SimpleNamespace(
            status=lambda: {"running": True, "host": "127.0.0.1", "port": 3333},
            stop=lambda timeout_seconds=5.0: {
                "status": "ok",
                "summary": "stopped",
                "timeout": timeout_seconds,
            },
        )
    )

    status = get_gdb_server_status(session)
    stopped = stop_gdb_server(session, timeout_seconds=2.5)

    assert status["status"] == "ok"
    assert status["running"] is True
    assert stopped["status"] == "ok"
    assert stopped["timeout"] == 2.5


def test_runtime_status_reflects_running_process() -> None:
    runtime = GdbServerRuntime()
    runtime._process = _FakeProcess()
    runtime._host = "127.0.0.1"
    runtime._port = 3333

    status = runtime.status()

    assert status["running"] is True
    assert status["state"] == "running"
    assert status["backend"] == "pyocd"


def test_runtime_stop_terminates_process() -> None:
    runtime = GdbServerRuntime()
    runtime._process = _FakeProcess()
    runtime._host = "127.0.0.1"
    runtime._port = 3333

    result = runtime.stop(timeout_seconds=1.5)

    assert result["status"] == "ok"
    assert result["running"] is False
    assert result["exit_code"] == 0


def test_start_jlink_gdb_server_uses_session_defaults(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        gdb_server_tools,
        "_resolve_jlink_gdb_server_path",
        lambda exe_path=None: exe_path or r"E:\software\jlink\JLinkGDBServerCL.exe",
    )
    session = SimpleNamespace(
        config=SimpleNamespace(
            probe=SimpleNamespace(target="STM32F103C8", unique_id="240710115"),
        ),
        gdb_server=SimpleNamespace(
            start_jlink=lambda **kwargs: (
                calls.append(kwargs) or {"status": "ok", "summary": "started"}
            ),
        ),
    )

    result = start_jlink_gdb_server(session, speed=1000)

    assert result["status"] == "ok"
    assert calls == [
        {
            "target": "STM32F103C8",
            "serial_no": "240710115",
            "port": 2331,
            "interface": "swd",
            "speed": 1000,
            "exe_path": r"E:\software\jlink\JLinkGDBServerCL.exe",
            "cwd": r"E:\software\jlink",
        }
    ]


def test_start_jlink_gdb_server_requires_target(monkeypatch) -> None:
    monkeypatch.setattr(
        gdb_server_tools,
        "_resolve_jlink_gdb_server_path",
        lambda exe_path=None: exe_path or r"E:\software\jlink\JLinkGDBServerCL.exe",
    )
    session = SimpleNamespace(
        config=SimpleNamespace(
            probe=SimpleNamespace(target=None, unique_id=None),
        ),
        gdb_server=SimpleNamespace(),
    )

    result = start_jlink_gdb_server(session)

    assert result["status"] == "error"


def test_start_jlink_gdb_server_retries_without_serial_on_selection_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        gdb_server_tools,
        "_resolve_jlink_gdb_server_path",
        lambda exe_path=None: exe_path or r"E:\software\jlink\JLinkGDBServerCL.exe",
    )
    calls: list[dict] = []

    def _start_jlink(**kwargs):
        calls.append(kwargs)
        if kwargs["serial_no"] is not None:
            return {
                "status": "error",
                "summary": "startup failed",
                "log_tail": ["Could not select J-Link with specified S/N (240710115)."],
            }
        return {"status": "ok", "summary": "started"}

    session = SimpleNamespace(
        config=SimpleNamespace(
            probe=SimpleNamespace(target="STM32F103C8", unique_id="240710115"),
        ),
        gdb_server=SimpleNamespace(start_jlink=_start_jlink),
    )

    result = start_jlink_gdb_server(session)

    assert result["status"] == "ok"
    assert result["requested_serial_no"] == "240710115"
    assert len(calls) == 2
    assert calls[0]["serial_no"] == "240710115"
    assert calls[1]["serial_no"] is None


def test_jlink_status_and_stop_wrap_runtime() -> None:
    session = SimpleNamespace(
        gdb_server=SimpleNamespace(
            status=lambda: {
                "running": True,
                "backend": "jlink",
                "host": "127.0.0.1",
                "port": 2331,
            },
            stop=lambda timeout_seconds=5.0: {
                "status": "ok",
                "summary": "stopped",
                "timeout": timeout_seconds,
            },
        )
    )

    status = get_jlink_gdb_server_status(session)
    stopped = stop_jlink_gdb_server(session, timeout_seconds=2.0)

    assert status["status"] == "ok"
    assert status["running"] is True
    assert stopped["status"] == "ok"
    assert stopped["timeout"] == 2.0


def test_runtime_start_jlink_builds_expected_command(monkeypatch, tmp_path) -> None:
    started = {}

    class _PopenFake:
        def __init__(self, command, cwd, stdout, stderr, text):
            started["command"] = command
            started["cwd"] = cwd
            self.returncode = None

        def poll(self):
            return None

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

    monkeypatch.setattr(
        gdb_server_tools, "_resolve_jlink_gdb_server_path", lambda exe_path=None: exe_path
    )
    monkeypatch.setattr("McuBuddy.gdb_server.subprocess.Popen", _PopenFake)
    monkeypatch.setattr("McuBuddy.gdb_server.time.sleep", lambda *_args, **_kwargs: None)

    runtime = GdbServerRuntime()
    exe_path = str(tmp_path / "JLinkGDBServerCL.exe")
    (tmp_path / "JLinkGDBServerCL.exe").write_text("", encoding="utf-8")

    result = runtime.start_jlink(
        target="STM32F103C8",
        serial_no="240710115",
        port=2331,
        interface="swd",
        speed=4000,
        exe_path=exe_path,
        cwd=str(tmp_path),
    )

    assert result["status"] == "ok"
    assert result["backend"] == "jlink"
    assert started["command"] == [
        exe_path,
        "-device",
        "STM32F103C8",
        "-if",
        "SWD",
        "-speed",
        "4000",
        "-port",
        "2331",
        "-noir",
        "-select",
        "usb=240710115",
    ]
