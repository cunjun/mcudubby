from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import BinaryIO, Any
from urllib.request import Request, urlopen

from . import __version__
from .chip_matcher import normalize_chip_name


_PY32_PACK = {
    "target": "py32f030x8",
    "filename": "Puya.PY32F0xx_DFP.1.2.8.pack",
    "download_url": "https://www.puyasemi.com/uploadfiles/Puya.PY32F0xx_DFP.1.2.8.pack",
    "sha256": "bb434a82e1a07973b3dcd9045a21748fa390b14c36fc90b9d27b4d005b65b566",
}
_MAX_PACK_DOWNLOAD_SIZE = 64 * 1024 * 1024


def _pack_for_target(target: str) -> dict[str, str] | None:
    normalized = normalize_chip_name(target)
    return _PY32_PACK if normalized == _PY32_PACK["target"] else None


def _default_search_roots() -> list[Path]:
    return [Path.cwd() / "packs", Path(__file__).resolve().parents[2] / "packs"]


def discover_pack_paths(
    target: str, search_roots: Iterable[str | Path] | None = None
) -> list[str]:
    pack = _pack_for_target(target)
    if pack is None:
        return []
    roots = [Path(root).expanduser().resolve() for root in (search_roots or _default_search_roots())]
    discovered: list[str] = []
    seen: set[Path] = set()
    for root in roots:
        pack_path = root / pack["filename"]
        if not pack_path.is_file() or _sha256(pack_path) != pack["sha256"]:
            continue
        resolved = pack_path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            discovered.append(str(resolved))
    return discovered


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def diagnose_pack(
    target: str,
    *,
    search_roots: Iterable[str | Path] | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    pack = _pack_for_target(target)
    if pack is None:
        return {
            "status": "error",
            "summary": f"No managed CMSIS-Pack metadata is available for target {target}.",
            "target": normalize_chip_name(target),
        }

    roots = [Path(root).expanduser().resolve() for root in (search_roots or _default_search_roots())]
    expected = (expected_sha256 or pack["sha256"]).lower()
    for root in roots:
        candidate = root / pack["filename"]
        if not candidate.is_file():
            continue
        actual = _sha256(candidate)
        verified = actual == expected
        return {
            "status": "ok" if verified else "error",
            "summary": (
                f"Verified CMSIS-Pack at {candidate}."
                if verified
                else f"CMSIS-Pack checksum mismatch at {candidate}."
            ),
            "target": pack["target"],
            "required_pack": pack["filename"],
            "path": str(candidate),
            "sha256": actual,
            "expected_sha256": expected,
            "sha256_verified": verified,
            "download_url": pack["download_url"],
        }

    recommended = roots[0]
    return {
        "status": "warning",
        "summary": f"Required CMSIS-Pack {pack['filename']} was not found.",
        "target": pack["target"],
        "required_pack": pack["filename"],
        "download_url": pack["download_url"],
        "expected_sha256": expected,
        "recommended_directory": str(recommended),
        "recommended_path": str(recommended / pack["filename"]),
    }


def install_pack(
    target: str,
    *,
    destination: str | Path,
    confirm: bool = False,
    expected_sha256: str | None = None,
    opener: Callable[[Request], BinaryIO] = urlopen,
) -> dict[str, Any]:
    pack = _pack_for_target(target)
    if pack is None:
        return {
            "status": "error",
            "summary": f"No managed CMSIS-Pack metadata is available for target {target}.",
            "target": normalize_chip_name(target),
        }
    if not confirm:
        return {
            "status": "error",
            "summary": "CMSIS-Pack installation requires explicit confirmation.",
            "confirmation_required": True,
            "target": pack["target"],
            "download_url": pack["download_url"],
        }

    destination_path = Path(destination).expanduser().resolve()
    destination_path.mkdir(parents=True, exist_ok=True)
    output_path = destination_path / pack["filename"]
    temporary_path = output_path.with_suffix(output_path.suffix + ".download")
    expected = (expected_sha256 or pack["sha256"]).lower()
    request = Request(pack["download_url"], headers={"User-Agent": f"McuBuddy/{__version__}"})

    try:
        digest = hashlib.sha256()
        downloaded_size = 0
        with opener(request) as response, temporary_path.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                downloaded_size += len(chunk)
                if downloaded_size > _MAX_PACK_DOWNLOAD_SIZE:
                    raise ValueError(
                        f"CMSIS-Pack download exceeds {_MAX_PACK_DOWNLOAD_SIZE} bytes"
                    )
                handle.write(chunk)
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual != expected:
            temporary_path.unlink(missing_ok=True)
            return {
                "status": "error",
                "summary": "Downloaded CMSIS-Pack checksum did not match the trusted value.",
                "target": pack["target"],
                "expected_sha256": expected,
                "actual_sha256": actual,
            }
        os.replace(temporary_path, output_path)
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        return {
            "status": "error",
            "summary": f"CMSIS-Pack installation failed: {exc}",
            "target": pack["target"],
        }

    return {
        "status": "ok",
        "summary": f"Installed and verified {pack['filename']}.",
        "target": pack["target"],
        "path": str(output_path),
        "sha256": expected,
        "download_url": pack["download_url"],
    }
