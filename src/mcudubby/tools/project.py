from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from ..session import SessionState
from .configuration import configure_build, configure_elf


_TARGET_RE = re.compile(r"<TargetName>\s*([^<]+?)\s*</TargetName>", re.IGNORECASE)
_DEVICE_RE = re.compile(r"<Device>\s*([^<]+?)\s*</Device>", re.IGNORECASE)
_OUTPUT_RE = re.compile(r"<OutputName>\s*([^<]+?)\s*</OutputName>", re.IGNORECASE)
_OUTPUT_DIR_RE = re.compile(r"<OutputDirectory>\s*([^<]+?)\s*</OutputDirectory>", re.IGNORECASE)
_XML_FIELDS = {
    "TargetName": "targets",
    "Device": "devices",
    "OutputName": "output_names",
    "OutputDirectory": "output_dirs",
}


def discover_keil_projects(root: str, max_depth: int = 6) -> dict:
    """Discover Keil MDK projects and likely firmware outputs under a directory."""
    root_path = Path(root).expanduser()
    if not root_path.exists():
        return {
            "status": "error",
            "summary": f"Discovery root does not exist: {root}",
            "root": str(root_path),
        }

    projects = []
    for project_path in _iter_files(root_path, ("*.uvprojx", "*.uvproj"), max_depth=max_depth):
        projects.append(_describe_keil_project(project_path))

    return {
        "status": "ok",
        "summary": f"Found {len(projects)} Keil project(s).",
        "root": str(root_path),
        "projects": projects,
    }


def configure_keil_project(
    session: SessionState,
    root: str | None = None,
    project_path: str | None = None,
    uv4_path: str | None = None,
    target_name: str | None = None,
    elf_path: str | None = None,
    build_log_path: str | None = None,
    flash_log_path: str | None = None,
) -> dict:
    """Configure Keil build and ELF paths using explicit values or auto-discovery."""
    if project_path is None:
        if root is None:
            return {
                "status": "error",
                "summary": "Pass project_path or root for Keil project discovery.",
            }
        discovery = discover_keil_projects(root)
        if discovery["status"] != "ok":
            return discovery
        projects = discovery["projects"]
        if not projects:
            return {
                "status": "error",
                "summary": f"No Keil project found under {root}.",
                "discovery": discovery,
            }
        selected = projects[0]
        project_path = selected["project_path"]
    else:
        selected = _describe_keil_project(Path(project_path))
        discovery = None

    selected_target = target_name or _first_or_none(selected["targets"])
    selected_elf = elf_path or _pick_firmware_path(selected["firmware_outputs"])

    build_result = configure_build(
        session,
        uv4_path=uv4_path,
        project_path=project_path,
        target_name=selected_target,
        build_log_path=build_log_path,
        flash_log_path=flash_log_path,
    )
    elf_result = None
    if selected_elf:
        elf_result = configure_elf(session, selected_elf)

    missing = []
    if uv4_path is None and not session.config.build.uv4_path:
        missing.append("uv4_path")
    if selected_target is None:
        missing.append("target_name")
    if selected_elf is None:
        missing.append("elf_path")

    status = "partial" if missing else "ok"
    summary = "Configured Keil project."
    if missing:
        summary += " Missing " + ", ".join(missing) + "."

    return {
        "status": status,
        "summary": summary,
        "selected_project": selected,
        "selected_target": selected_target,
        "selected_elf": selected_elf,
        "build": build_result,
        "elf": elf_result,
        "missing": missing,
        "discovery": discovery,
        "config": session.config.model_dump(),
    }


def _describe_keil_project(project_path: Path) -> dict[str, Any]:
    project_path = project_path.expanduser()
    project_dir = project_path.parent
    uvoptx_path = project_path.with_suffix(".uvoptx")
    metadata = _extract_keil_metadata([project_path, uvoptx_path])

    firmware_outputs = _find_firmware_outputs(project_dir, metadata["output_dirs"])

    return {
        "project_path": str(project_path),
        "project_dir": str(project_dir),
        "uvoptx_path": str(uvoptx_path) if uvoptx_path.exists() else None,
        "targets": metadata["targets"],
        "devices": metadata["devices"],
        "output_names": metadata["output_names"],
        "output_dirs": metadata["output_dirs"],
        "firmware_outputs": firmware_outputs,
    }


def _extract_keil_metadata(paths: list[Path]) -> dict[str, list[str]]:
    metadata = {field: [] for field in _XML_FIELDS.values()}
    for path in paths:
        if not path.exists():
            continue
        parsed = _read_xml_values(path)
        if parsed is None:
            parsed = _read_text_values(path)
        for key, values in parsed.items():
            metadata[key].extend(values)
    return {key: _dedupe(values) for key, values in metadata.items()}


def _read_xml_values(path: Path) -> dict[str, list[str]] | None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None

    values = {field: [] for field in _XML_FIELDS.values()}
    for element in root.iter():
        field = _XML_FIELDS.get(_local_name(element.tag))
        if field and element.text:
            values[field].append(element.text)
    return values


def _read_text_values(path: Path) -> dict[str, list[str]]:
    text = _read_text(path)
    return {
        "targets": _TARGET_RE.findall(text),
        "devices": _DEVICE_RE.findall(text),
        "output_names": _OUTPUT_RE.findall(text),
        "output_dirs": _OUTPUT_DIR_RE.findall(text),
    }


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_firmware_outputs(project_dir: Path, output_dirs: list[str]) -> list[dict[str, Any]]:
    search_roots = [
        *[_resolve_project_path(project_dir, output_dir) for output_dir in output_dirs],
        project_dir / "Objects",
        project_dir / "OBJ",
        project_dir / "Output",
        project_dir,
    ]
    seen: set[Path] = set()
    outputs = []
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in sorted(search_root.glob("*")):
            if path.suffix.lower() not in {".axf", ".elf", ".hex", ".bin"}:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            stat = path.stat()
            outputs.append(
                {
                    "path": str(path),
                    "kind": path.suffix.lower().lstrip("."),
                    "size_bytes": stat.st_size,
                    "last_modified": stat.st_mtime,
                }
            )
    outputs.sort(key=lambda item: (item["kind"] not in {"axf", "elf"}, -item["last_modified"]))
    return outputs


def _resolve_project_path(project_dir: Path, value: str) -> Path:
    path = Path(value.strip().replace("\\", "/"))
    if path.is_absolute():
        return path
    return project_dir / path


def _iter_files(root: Path, patterns: tuple[str, ...], max_depth: int) -> list[Path]:
    results: list[Path] = []
    for pattern in patterns:
        for path in root.rglob(pattern):
            try:
                depth = len(path.relative_to(root).parts) - 1
            except ValueError:
                continue
            if depth <= max_depth:
                results.append(path)
    return sorted(set(results))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _dedupe(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        clean = value.strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _first_or_none(values: list[str]) -> str | None:
    return values[0] if values else None


def _pick_firmware_path(outputs: list[dict[str, Any]]) -> str | None:
    for output in outputs:
        if output["kind"] in {"axf", "elf"}:
            return output["path"]
    return None
