from __future__ import annotations

from McuBuddy.skill_installer import install_skill


def _skill_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("# mcubug\n", encoding="utf-8")
    return source


def test_install_skill_writes_codex_target(tmp_path) -> None:
    source = _skill_source(tmp_path)

    report = install_skill(source=source, home=tmp_path / "home", target="codex")

    assert report["status"] == "ok"
    assert (tmp_path / "home" / ".codex" / "skills" / "mcubug" / "SKILL.md").is_file()
    assert any("does not register" in step for step in report["next_steps"])
    assert any("windows-mcp-config-example.md" in step for step in report["next_steps"])


def test_install_skill_dry_run_does_not_write(tmp_path) -> None:
    source = _skill_source(tmp_path)

    report = install_skill(source=source, home=tmp_path / "home", target="both", dry_run=True)

    assert report["status"] == "ok"
    assert len(report["entries"]) == 2
    assert {entry["status"] for entry in report["entries"]} == {"would_install"}
    assert not (tmp_path / "home" / ".codex").exists()
    assert not (tmp_path / "home" / ".claude").exists()


def test_install_skill_requires_force_for_existing_target(tmp_path) -> None:
    source = _skill_source(tmp_path)
    install_skill(source=source, home=tmp_path / "home", target="codex")

    duplicate = install_skill(source=source, home=tmp_path / "home", target="codex")

    assert duplicate["status"] == "error"
    assert "already exists" in duplicate["summary"]


def test_install_skill_force_replaces_existing_target(tmp_path) -> None:
    source = _skill_source(tmp_path)
    install_skill(source=source, home=tmp_path / "home", target="codex")
    (source / "SKILL.md").write_text("# updated\n", encoding="utf-8")

    report = install_skill(source=source, home=tmp_path / "home", target="codex", force=True)

    assert report["status"] == "ok"
    installed = tmp_path / "home" / ".codex" / "skills" / "mcubug" / "SKILL.md"
    assert installed.read_text(encoding="utf-8") == "# updated\n"
