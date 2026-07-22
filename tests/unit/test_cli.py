from __future__ import annotations

import json

import pytest

from McuBuddy import cli
from McuBuddy.config import load_config, parse_cli_overrides


def test_help_lists_management_commands(capsys) -> None:
    parser = cli.build_parser()

    try:
        parser.parse_args(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    output = capsys.readouterr().out
    assert "doctor" in output
    assert "config" in output
    assert "probes" in output
    assert "skill" in output


def test_config_generate_prints_toml(capsys) -> None:
    assert cli.main(["config", "generate"]) == 0

    output = capsys.readouterr().out
    assert "[server]" in output
    assert "[security]" in output
    assert 'tool_profile = "core"' in output


def test_config_validate_reports_invalid_profile(tmp_path, capsys) -> None:
    config = tmp_path / "mcubuddy.toml"
    config.write_text('[server]\ntool_profile = "expert"\n', encoding="utf-8")

    assert cli.main(["config", "validate", str(config)]) == 1

    output = capsys.readouterr().out
    assert "Configuration is invalid" in output
    assert "server.tool_profile" in output


def test_skill_install_dry_run_json(tmp_path, capsys) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("# mcubug\n", encoding="utf-8")

    assert (
        cli.main(
            [
                "skill",
                "install",
                "--target",
                "both",
                "--home",
                str(tmp_path / "home"),
                "--source",
                str(source),
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["target"] == "both"
    assert {entry["status"] for entry in report["entries"]} == {"would_install"}


def test_probes_list_json_uses_configured_backend(monkeypatch, tmp_path, capsys) -> None:
    config = tmp_path / "mcubuddy.toml"
    config.write_text('[probe]\nbackend = "jlink"\n', encoding="utf-8")
    calls = []

    class _Probe:
        def enumerate_probes(self):
            return [{"identifier": "J-Link", "unique_id": "abc"}]

    def fake_create_backend(name, **kwargs):
        calls.append((name, kwargs))
        return _Probe()

    monkeypatch.setattr(cli, "create_probe_backend", fake_create_backend)

    assert cli.main(["probes", "list", "--config", str(config), "--json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["probes"] == [{"identifier": "J-Link", "unique_id": "abc"}]
    assert calls[0][0] == "jlink"


def test_doctor_json_reports_loaded_config(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "build_doctor_report",
        lambda config: {
            "status": "warning",
            "summary": "doctor summary",
            "checks": [{"name": "probe", "status": "warning", "summary": "none"}],
            "profile": config.server.tool_profile,
        },
    )

    assert cli.main(["doctor", "--json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "warning"
    assert report["profile"] == "core"


def test_config_precedence_is_cli_over_environment_over_file(tmp_path) -> None:
    config_path = tmp_path / "mcubuddy.toml"
    config_path.write_text("[memory]\nmax_read_size = 512\n", encoding="utf-8")

    config = load_config(
        config_path,
        environ={"MCUBUDDY_MAX_READ_SIZE": "1024"},
        cli_overrides=parse_cli_overrides(["memory.max_read_size=2048"]),
    )

    assert config.memory.max_read_size == 2048


def test_tool_profile_environment_override_remains_normalized() -> None:
    config = load_config(environ={"MCUBUDDY_TOOL_PROFILE": " FULL "})

    assert config.server.tool_profile == "full"


def test_parse_cli_overrides_converts_scalar_values() -> None:
    overrides = parse_cli_overrides(
        [
            "memory.max_read_size=8192",
            "memory.allow_write=true",
            "probe.target=stm32f103c8",
        ]
    )

    assert overrides == {
        "memory": {"max_read_size": 8192, "allow_write": True},
        "probe": {"target": "stm32f103c8"},
    }


def test_config_show_applies_set_after_environment(monkeypatch, tmp_path, capsys) -> None:
    config_path = tmp_path / "mcubuddy.toml"
    config_path.write_text("[memory]\nmax_read_size = 512\n", encoding="utf-8")
    monkeypatch.setenv("MCUBUDDY_MAX_READ_SIZE", "1024")

    assert (
        cli.main(
            [
                "config",
                "show",
                "--config",
                str(config_path),
                "--set",
                "memory.max_read_size=2048",
                "--json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["memory"]["max_read_size"] == 2048


def test_unknown_cli_override_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown config override"):
        parse_cli_overrides(["memory.unknown_limit=1"])


def test_unknown_cli_override_returns_cli_usage_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["config", "show", "--set", "memory.unknown_limit=1"])

    assert exc_info.value.code == 2
    assert "Unknown config override memory.unknown_limit" in capsys.readouterr().err


def test_no_argument_startup_keeps_legacy_serve_behavior(monkeypatch) -> None:
    calls = []

    class _App:
        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr("McuBuddy.server.create_server", lambda *args, **kwargs: _App())

    assert cli.main([]) == 0
    assert calls == ["run"]


def test_serve_uses_effective_probe_backend(monkeypatch) -> None:
    captured = {}
    backend = object()

    class _App:
        def run(self) -> None:
            captured["ran"] = True

    def fake_create_server(session, *, tool_profile):
        captured["session"] = session
        captured["tool_profile"] = tool_profile
        return _App()

    monkeypatch.setattr("McuBuddy.server.create_server", fake_create_server)
    monkeypatch.setattr(cli, "create_probe_backend", lambda name, **kwargs: backend)

    assert cli.main(["serve", "--set", "probe.backend=jlink"]) == 0
    assert captured["session"].probe is backend
    assert captured["session"].config.probe.backend == "jlink"
    assert captured["tool_profile"] == "core"
    assert captured["ran"] is True


def test_doctor_config_error_keeps_json_schema_version(tmp_path, capsys) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text("[memory\n", encoding="utf-8")

    assert cli.main(["doctor", "--config", str(config_path), "--json"]) == 1

    report = json.loads(capsys.readouterr().out)
    assert set(report) == {
        "schema_version",
        "status",
        "summary",
        "version",
        "checks",
        "config",
    }
    assert report["schema_version"] == "1.0"
    assert report["status"] == "error"
    assert report["config"] is None
