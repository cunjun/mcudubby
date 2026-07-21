from __future__ import annotations

import argparse
import json
from typing import Any

from .config import (
    config_for_display,
    config_to_toml,
    load_config,
    validate_config_file,
)
from .doctor import build_doctor_report
from .session import SessionState, create_probe_backend
from .skill_installer import install_skill


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "serve"
    if command == "serve":
        return _serve()
    if command == "doctor":
        return _doctor(args)
    if command == "config":
        return _config(args)
    if command == "probes":
        return _probes(args)
    if command == "skill":
        return _skill(args)
    parser.error(f"unknown command: {command}")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="McuBuddy")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("serve", help="Start the MCP stdio server.")

    doctor = subparsers.add_parser("doctor", help="Check local runtime readiness.")
    doctor.add_argument("--config", help="Path to a McuBuddy TOML config file.")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    config = subparsers.add_parser("config", help="Generate, validate, or show config.")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("generate", help="Print a sample TOML configuration.")
    validate = config_sub.add_parser("validate", help="Validate a TOML configuration.")
    validate.add_argument("path", help="Path to the config file.")
    show = config_sub.add_parser("show", help="Show the effective configuration.")
    show.add_argument("--config", help="Path to a McuBuddy TOML config file.")
    show.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    probes = subparsers.add_parser("probes", help="Probe management commands.")
    probes_sub = probes.add_subparsers(dest="probes_command", required=True)
    probe_list = probes_sub.add_parser("list", help="List connected debug probes.")
    probe_list.add_argument("--config", help="Path to a McuBuddy TOML config file.")
    probe_list.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    skill = subparsers.add_parser("skill", help="Skill management commands.")
    skill_sub = skill.add_subparsers(dest="skill_command", required=True)
    install = skill_sub.add_parser("install", help="Install the mcubug assistant skill.")
    install.add_argument("--target", choices=["codex", "claude", "both"], default="codex")
    install.add_argument("--home", help="Home directory used to resolve assistant directories.")
    install.add_argument("--source", help="Source mcubug skill directory.")
    install.add_argument("--dry-run", action="store_true", help="Preview without writing files.")
    install.add_argument("--force", action="store_true", help="Replace existing installs.")
    install.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    return parser


def _serve() -> int:
    from .server import mcp

    mcp.run()
    return 0


def _doctor(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except Exception as exc:
        report = {
            "status": "error",
            "summary": f"Configuration failed to load: {exc}",
            "checks": [{"name": "config", "status": "error", "summary": str(exc)}],
        }
    else:
        report = build_doctor_report(config)
    _print_report(report, as_json=args.json)
    return 0 if report["status"] in ("ok", "warning") else 1


def _config(args: argparse.Namespace) -> int:
    if args.config_command == "generate":
        print(config_to_toml(), end="")
        return 0
    if args.config_command == "validate":
        _, errors = validate_config_file(args.path)
        if errors:
            print("Configuration is invalid.")
            for error in errors:
                loc = ".".join(str(part) for part in error.get("loc", ()))
                print(f"- {loc}: {error.get('msg')}")
            return 1
        print("Configuration is valid.")
        return 0
    if args.config_command == "show":
        config = load_config(args.config)
        _print_report(config_for_display(config), as_json=args.json)
        return 0
    raise ValueError(f"Unknown config command: {args.config_command}")


def _probes(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    try:
        session = SessionState()
        session.config = config
        session.probe = create_probe_backend(
            config.probe.backend,
            jlink_dll_path=config.probe.jlink_dll_path,
            probe_rs_sidecar_path=config.probe.probe_rs_sidecar_path,
        )
        probes = session.probe.enumerate_probes()
        report = {
            "status": "ok",
            "summary": f"Found {len(probes)} connected probe(s)."
            if probes
            else "No probes detected. Check USB connection and driver installation.",
            "probes": probes,
        }
    except Exception as exc:
        report = {"status": "warning", "summary": f"Probe discovery failed: {exc}", "probes": []}
    _print_report(report, as_json=args.json)
    return 0


def _skill(args: argparse.Namespace) -> int:
    if args.skill_command != "install":
        raise ValueError(f"Unknown skill command: {args.skill_command}")
    report = install_skill(
        target=args.target,
        home=args.home,
        source=args.source,
        dry_run=args.dry_run,
        force=args.force,
    )
    _print_report(report, as_json=args.json)
    return 0 if report["status"] == "ok" else 1


def _print_report(report: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        return
    summary = report.get("summary")
    if summary:
        print(summary)
    if "checks" in report:
        for check in report["checks"]:
            print(f"- {check['name']}: {check['status']} - {check['summary']}")
    if "probes" in report:
        for index, probe in enumerate(report["probes"], start=1):
            print(f"{index}. {probe}")
    if "entries" in report:
        for entry in report["entries"]:
            print(f"{entry['kind']}: {entry['path']} ({entry['status']})")
    if "next_steps" in report:
        for step in report["next_steps"]:
            print(f"- {step}")
    if not any(key in report for key in ("checks", "probes", "entries")) and isinstance(
        report, dict
    ):
        for key, value in report.items():
            print(f"{key}: {value}")
