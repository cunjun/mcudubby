from __future__ import annotations

from types import SimpleNamespace

import McuBuddy.backends.probe.pyocd_backend as pyocd_backend


class _FakeSession:
    def __init__(self) -> None:
        self.target = SimpleNamespace()
        self.opened = False

    def open(self) -> None:
        self.opened = True


def test_pyocd_backend_connect_uses_first_successful_attempt(monkeypatch) -> None:
    attempts: list[dict] = []

    def _session_with_chosen_probe(**kwargs):
        attempts.append(kwargs)
        return _FakeSession()

    monkeypatch.setattr(
        pyocd_backend,
        "ConnectHelper",
        SimpleNamespace(session_with_chosen_probe=_session_with_chosen_probe),
    )

    backend = pyocd_backend.PyOcdProbeBackend()
    result = backend.connect(target="stm32f103c8", unique_id="abc123")

    assert result["status"] == "ok"
    assert result["frequency_hz"] == 4000000
    assert result["connect_mode"] == "attach"
    assert result["attempted_configs"] == [{"frequency": 4000000, "connect_mode": "attach"}]
    assert attempts[0]["target_override"] == "stm32f103c8"
    assert attempts[0]["unique_id"] == "abc123"
    assert attempts[0]["pack"] is None


def test_pyocd_backend_connect_passes_pack_paths(monkeypatch) -> None:
    attempts: list[dict] = []

    def _session_with_chosen_probe(**kwargs):
        attempts.append(kwargs)
        return _FakeSession()

    monkeypatch.setattr(
        pyocd_backend,
        "ConnectHelper",
        SimpleNamespace(session_with_chosen_probe=_session_with_chosen_probe),
    )

    backend = pyocd_backend.PyOcdProbeBackend()
    backend.set_pack_paths([r"d:\packs\Vendor.Device.1.0.0.pack"])
    result = backend.connect(target="vendor_device")

    assert result["status"] == "ok"
    assert result["pack_paths"] == [r"d:\packs\Vendor.Device.1.0.0.pack"]
    assert attempts[0]["pack"] == [r"d:\packs\Vendor.Device.1.0.0.pack"]


def test_pyocd_backend_connect_auto_discovers_py32_pack(monkeypatch) -> None:
    attempts: list[dict] = []
    pack_path = r"d:\packs\Puya.PY32F0xx_DFP.1.2.8.pack"

    def _session_with_chosen_probe(**kwargs):
        attempts.append(kwargs)
        return _FakeSession()

    monkeypatch.setattr(
        pyocd_backend,
        "ConnectHelper",
        SimpleNamespace(session_with_chosen_probe=_session_with_chosen_probe),
    )
    monkeypatch.setattr(
        pyocd_backend,
        "_discover_default_pack_paths",
        lambda target: [pack_path] if target == "py32f030x8" else [],
    )

    backend = pyocd_backend.PyOcdProbeBackend()
    result = backend.connect(target="py32f030x8")

    assert result["status"] == "ok"
    assert result["pack_paths"] == [pack_path]
    assert attempts[0]["pack"] == [pack_path]


def test_pyocd_backend_connect_falls_back_to_under_reset(monkeypatch) -> None:
    attempts: list[dict] = []

    def _session_with_chosen_probe(**kwargs):
        attempts.append(kwargs)
        if len(attempts) < 3:
            return None
        return _FakeSession()

    monkeypatch.setattr(
        pyocd_backend,
        "ConnectHelper",
        SimpleNamespace(session_with_chosen_probe=_session_with_chosen_probe),
    )

    backend = pyocd_backend.PyOcdProbeBackend()
    result = backend.connect(target="stm32f103c8")

    assert result["status"] == "ok"
    assert result["frequency_hz"] == 1000000
    assert result["connect_mode"] == "under-reset"
    assert result["attempted_configs"] == [
        {"frequency": 4000000, "connect_mode": "attach"},
        {"frequency": 1000000, "connect_mode": "attach"},
        {"frequency": 1000000, "connect_mode": "under-reset"},
    ]
