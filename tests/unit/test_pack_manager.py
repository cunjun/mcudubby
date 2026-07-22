from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO

from McuBuddy import pack_manager
from McuBuddy.pack_manager import diagnose_pack, discover_pack_paths, install_pack
from McuBuddy.server import create_server
from McuBuddy.session import SessionState


def test_diagnose_py32_pack_returns_actionable_missing_report(tmp_path) -> None:
    result = diagnose_pack("PY32F030X8", search_roots=[tmp_path])

    assert result["status"] == "warning"
    assert result["target"] == "py32f030x8"
    assert result["required_pack"] == "Puya.PY32F0xx_DFP.1.2.8.pack"
    assert result["download_url"].startswith("https://www.puyasemi.com/")
    assert result["recommended_directory"] == str(tmp_path)


def test_diagnose_py32_pack_reports_verified_local_pack(tmp_path) -> None:
    payload = b"official pack bytes"
    pack = tmp_path / "Puya.PY32F0xx_DFP.1.2.8.pack"
    pack.write_bytes(payload)

    result = diagnose_pack(
        "py32f030x8",
        search_roots=[tmp_path],
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )

    assert result["status"] == "ok"
    assert result["path"] == str(pack.resolve())
    assert result["sha256_verified"] is True


def test_install_pack_downloads_then_verifies_before_replacing_destination(tmp_path) -> None:
    payload = b"pack archive"
    expected = hashlib.sha256(payload).hexdigest()

    result = install_pack(
        "py32f030x8",
        destination=tmp_path,
        confirm=True,
        expected_sha256=expected,
        opener=lambda request: BytesIO(payload),
    )

    installed = tmp_path / "Puya.PY32F0xx_DFP.1.2.8.pack"
    assert result["status"] == "ok"
    assert installed.read_bytes() == payload
    assert result["sha256"] == expected


def test_install_pack_requires_confirmation(tmp_path) -> None:
    result = install_pack("py32f030x8", destination=tmp_path, confirm=False)

    assert result["status"] == "error"
    assert result["confirmation_required"] is True
    assert list(tmp_path.iterdir()) == []


def test_install_pack_rejects_oversized_download(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pack_manager, "_MAX_PACK_DOWNLOAD_SIZE", 4)

    result = install_pack(
        "py32f030x8",
        destination=tmp_path,
        confirm=True,
        opener=lambda request: BytesIO(b"12345"),
    )

    assert result["status"] == "error"
    assert "exceeds" in result["summary"]
    assert list(tmp_path.iterdir()) == []


def test_auto_discovery_uses_only_the_exact_verified_managed_pack(
    tmp_path, monkeypatch
) -> None:
    payload = b"trusted pack"
    trusted = tmp_path / "Puya.PY32F0xx_DFP.1.2.8.pack"
    trusted.write_bytes(payload)
    (tmp_path / "Puya.PY32F0xx_DFP.9.9.9.pack").write_bytes(b"unmanaged")
    monkeypatch.setitem(
        pack_manager._PY32_PACK, "sha256", hashlib.sha256(payload).hexdigest()
    )

    assert discover_pack_paths("PY32F030X8", [tmp_path]) == [str(trusted.resolve())]

    trusted.write_bytes(b"tampered")
    assert discover_pack_paths("PY32F030X8", [tmp_path]) == []


def test_pack_management_has_agent_tool_parity() -> None:
    app = create_server(SessionState())

    assert {"pack_diagnose", "pack_install"} <= set(app._tool_manager._tools)
    diagnose_tool = app._tool_manager.get_tool("pack_diagnose")
    diagnose_result = asyncio.run(diagnose_tool.run({"target": "unknown"}))
    assert diagnose_result["status"] == "error"

    install_tool = app._tool_manager.get_tool("pack_install")
    blocked = asyncio.run(install_tool.run({"target": "PY32F030X8"}))
    assert blocked["status"] == "error"
    assert blocked["safety"]["level"] == "persistent-destructive"
