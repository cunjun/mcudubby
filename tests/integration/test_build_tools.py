import subprocess
from pathlib import Path

from McuBuddy.config import BuildConfig, ElfConfig
from McuBuddy.session import SessionState
from McuBuddy.tools.build import build_project, flash_firmware


class _FakeBuildRuntime:
    def __init__(self) -> None:
        self.calls = []

    def build(self, build: BuildConfig, elf: ElfConfig, timeout_seconds: int = 120) -> dict:
        self.calls.append(("build", build, elf, timeout_seconds))
        return {
            "status": "ok",
            "summary": "fake build ok",
            "firmware": {"path": elf.path},
        }

    def flash(self, build: BuildConfig, elf: ElfConfig, timeout_seconds: int = 120) -> dict:
        self.calls.append(("flash", build, elf, timeout_seconds))
        return {
            "status": "ok",
            "summary": "fake flash ok",
            "firmware": {"path": elf.path},
        }


def test_build_project_uses_runtime_config() -> None:
    session = SessionState()
    session.config.build.uv4_path = r"E:\software\MDK\UV4\UV4.exe"
    session.config.build.project_path = r"d:\demo\app.uvprojx"
    session.config.build.target_name = "demo_target"
    session.config.elf.path = r"d:\demo\app.axf"
    session.build = _FakeBuildRuntime()

    result = build_project(session, timeout_seconds=33)

    assert result["status"] == "ok"
    assert session.build.calls[0][0] == "build"
    assert session.build.calls[0][1].target_name == "demo_target"
    assert session.build.calls[0][2].path == r"d:\demo\app.axf"
    assert session.build.calls[0][3] == 33


def test_flash_firmware_requires_confirmation_before_runtime_call() -> None:
    session = SessionState()
    session.build = _FakeBuildRuntime()

    result = flash_firmware(session, timeout_seconds=44)

    assert result["status"] == "error"
    assert result["safety"]["requires_confirmation"] is True
    assert session.build.calls == []


def test_flash_firmware_uses_runtime_config_when_confirmed() -> None:
    session = SessionState()
    session.config.build.uv4_path = r"E:\software\MDK\UV4\UV4.exe"
    session.config.build.project_path = r"d:\demo\app.uvprojx"
    session.config.build.target_name = "demo_target"
    session.config.elf.path = r"d:\demo\app.axf"
    session.build = _FakeBuildRuntime()

    result = flash_firmware(session, timeout_seconds=44, confirm=True)

    assert result["status"] == "ok"
    assert session.build.calls[0][0] == "flash"
    assert session.build.calls[0][1].project_path == r"d:\demo\app.uvprojx"
    assert session.build.calls[0][2].path == r"d:\demo\app.axf"
    assert session.build.calls[0][3] == 44


def test_keil_build_runtime_collects_firmware_info(tmp_path: Path) -> None:
    from McuBuddy.build_runtime import KeilBuildRuntime

    axf = tmp_path / "demo.axf"
    axf.write_bytes(b"demo")
    hex_path = tmp_path / "demo.hex"
    hex_path.write_text(":00000001FF", encoding="utf-8")

    info = KeilBuildRuntime._collect_firmware_info(str(axf))

    assert info is not None
    assert info["exists"] is True
    assert info["hex_exists"] is True
    assert info["path"].endswith("demo.axf")


def test_keil_build_runtime_resolves_log_path_to_existing_output_dir(tmp_path: Path) -> None:
    from McuBuddy.build_runtime import KeilBuildRuntime

    project_dir = tmp_path / "MDK-ARM"
    objects_dir = project_dir / "Objects"
    objects_dir.mkdir(parents=True)
    project_path = project_dir / "Demo.uvprojx"
    project_path.write_text("<Project />", encoding="utf-8")

    log_path = KeilBuildRuntime._resolve_log_path(None, project_path, "McuBuddy_build.log")

    assert log_path == objects_dir / "McuBuddy_build.log"


def test_keil_build_runtime_creates_configured_log_parent(tmp_path: Path) -> None:
    from McuBuddy.build_runtime import KeilBuildRuntime

    project_path = tmp_path / "MDK-ARM" / "Demo.uvprojx"
    project_path.parent.mkdir()
    project_path.write_text("<Project />", encoding="utf-8")
    configured_log = tmp_path / "logs" / "build.log"

    log_path = KeilBuildRuntime._resolve_log_path(
        str(configured_log),
        project_path,
        "McuBuddy_build.log",
    )

    assert log_path == configured_log
    assert configured_log.parent.exists()


def test_keil_build_rejects_stale_success_log_when_command_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from McuBuddy.build_runtime import KeilBuildRuntime

    build, elf = _keil_runtime_config(tmp_path, "build.log")
    log_path = Path(build.build_log_path or "")
    log_path.write_text("0 Error(s)", encoding="utf-8")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "failed"),
    )

    result = KeilBuildRuntime().build(build, elf)

    assert result["status"] == "error"
    assert not log_path.exists()


def test_keil_flash_rejects_stale_success_log_when_command_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from McuBuddy.build_runtime import KeilBuildRuntime

    build, elf = _keil_runtime_config(tmp_path, "flash.log")
    log_path = Path(build.flash_log_path or "")
    log_path.write_text("Verify OK\nApplication running", encoding="utf-8")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "failed"),
    )

    result = KeilBuildRuntime().flash(build, elf)

    assert result["status"] == "error"
    assert not log_path.exists()


def test_keil_build_accepts_success_markers_from_fresh_log(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from McuBuddy.build_runtime import KeilBuildRuntime

    build, elf = _keil_runtime_config(tmp_path, "build.log")

    def run(command, **kwargs):
        Path(command[-1]).write_text("0 Error(s)", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)

    result = KeilBuildRuntime().build(build, elf)

    assert result["status"] == "ok"


def test_keil_flash_accepts_success_markers_from_fresh_log(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from McuBuddy.build_runtime import KeilBuildRuntime

    build, elf = _keil_runtime_config(tmp_path, "flash.log")

    def run(command, **kwargs):
        Path(command[-1]).write_text("Verify OK\nApplication running", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)

    result = KeilBuildRuntime().flash(build, elf)

    assert result["status"] == "ok"


def _keil_runtime_config(tmp_path: Path, log_name: str) -> tuple[BuildConfig, ElfConfig]:
    uv4_path = tmp_path / "UV4.exe"
    uv4_path.write_text("", encoding="utf-8")
    project_path = tmp_path / "firmware.uvprojx"
    project_path.write_text("", encoding="utf-8")
    log_path = tmp_path / log_name
    build = BuildConfig(
        uv4_path=str(uv4_path),
        project_path=str(project_path),
        target_name="test",
        build_log_path=str(log_path),
        flash_log_path=str(log_path),
    )
    return build, ElfConfig()
