from __future__ import annotations

import json

from McuBuddy import cli


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
