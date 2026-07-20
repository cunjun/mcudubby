from McuBuddy.config import ConnectAttempt, get_builtin_profiles
from McuBuddy.session import SessionState
from McuBuddy.tools.configuration import (
    configure_build,
    configure_elf,
    configure_log,
    configure_probe,
    connect_with_config,
    get_target_info,
    load_demo_profile,
    match_chip_name,
)


def test_builtin_profile_exists() -> None:
    profiles = get_builtin_profiles()
    assert "stm32l4_atk_led_demo" in profiles
    assert "py32f030x8_cmsis_dap" in profiles


def test_load_demo_profile_updates_runtime_config() -> None:
    session = SessionState()
    result = load_demo_profile(session, "stm32l4_atk_led_demo")

    assert result["status"] == "ok"
    assert session.config.active_profile == "stm32l4_atk_led_demo"
    assert session.config.probe.target == "stm32l496vetx"
    assert session.config.log.baudrate == 115200
    assert session.config.build.target_name is None


def test_load_py32_profile_sets_safe_cmsis_dap_defaults() -> None:
    session = SessionState()
    result = load_demo_profile(session, "py32f030x8_cmsis_dap")

    assert result["status"] == "ok"
    assert session.config.active_profile == "py32f030x8_cmsis_dap"
    assert session.config.probe.backend == "pyocd"
    assert session.config.probe.target == "py32f030x8"
    assert [attempt.model_dump() for attempt in session.config.probe.connect_attempts] == [
        {"frequency": 100000, "connect_mode": "attach"},
        {"frequency": 100000, "connect_mode": "under-reset"},
    ]


def test_configure_probe_overrides_target() -> None:
    session = SessionState()
    result = configure_probe(session, target="stm32l4x", unique_id="abc123")
    assert result["status"] == "ok"
    assert session.config.probe.target == "stm32l4x"
    assert session.config.probe.unique_id == "abc123"


def test_configure_probe_sets_pack_paths() -> None:
    session = SessionState()
    result = configure_probe(
        session,
        target="vendor_part",
        backend="pyocd",
        pack_path=r"d:\packs\Vendor.Device.1.0.0.pack",
    )

    assert result["status"] == "ok"
    assert session.config.probe.pack_paths == [r"d:\packs\Vendor.Device.1.0.0.pack"]

    configure_probe(session, pack_path=r"d:\packs\Vendor.Device.1.0.0.pack")
    assert session.config.probe.pack_paths == [r"d:\packs\Vendor.Device.1.0.0.pack"]


def test_configure_probe_sets_custom_connect_attempts() -> None:
    session = SessionState()
    attempts = [
        {"frequency": 4000000, "connect_mode": "attach"},
        {"frequency": 100000, "connect_mode": "under-reset"},
    ]

    result = configure_probe(session, target="vendor_part", connect_attempts=attempts)

    assert result["status"] == "ok"
    assert [attempt.model_dump() for attempt in session.config.probe.connect_attempts] == attempts


def test_configure_probe_validates_before_replacing_or_disconnecting_backend(monkeypatch) -> None:
    class _Probe:
        def __init__(self) -> None:
            self.disconnect_calls = 0

        def disconnect(self) -> dict:
            self.disconnect_calls += 1
            return {"status": "ok"}

    session = SessionState()
    original_probe = _Probe()
    session.probe = original_probe
    original_config = session.config.model_copy(deep=True)
    replacement_created = False

    def create_replacement(*args, **kwargs):
        nonlocal replacement_created
        replacement_created = True
        return _Probe()

    monkeypatch.setattr(
        "McuBuddy.tools.configuration.create_probe_backend",
        create_replacement,
    )

    result = configure_probe(
        session,
        backend="jlink",
        connect_attempts=[{"frequency": 100_000, "connect_mode": "invalid"}],
    )

    assert result["status"] == "error"
    assert session.probe is original_probe
    assert session.config == original_config
    assert original_probe.disconnect_calls == 0
    assert replacement_created is False


def test_configure_log_overrides_port() -> None:
    session = SessionState()
    result = configure_log(session, uart_port="COM7", uart_baudrate=9600)
    assert result["status"] == "ok"
    assert session.config.log.port == "COM7"
    assert session.config.log.baudrate == 9600


def test_configure_elf_sets_path() -> None:
    session = SessionState()
    result = configure_elf(session, elf_path=r"d:\demo\firmware.axf")
    assert result["status"] == "ok"
    assert session.config.elf.path == r"d:\demo\firmware.axf"


def test_configure_build_sets_keil_params() -> None:
    session = SessionState()
    load_demo_profile(session, "stm32l4_atk_led_demo")
    result = configure_build(
        session,
        uv4_path=r"E:\software\MDK\UV4\UV4.exe",
        project_path=r"d:\demo\firmware.uvprojx",
        target_name="demo_target",
    )
    assert result["status"] == "ok"
    assert session.config.build.uv4_path == r"E:\software\MDK\UV4\UV4.exe"
    assert session.config.build.project_path == r"d:\demo\firmware.uvprojx"
    assert session.config.build.target_name == "demo_target"


def test_match_chip_name_resolves_known_jlink_alias() -> None:
    result = match_chip_name("STM32F103C8T6", backend="jlink")

    assert result["status"] == "ok"
    assert result["matched_target"] == "STM32F103C8"
    assert result["confidence"] == "high"


def test_configure_probe_normalizes_known_pyocd_alias() -> None:
    session = SessionState()

    result = configure_probe(session, target="STM32L496VE", backend="pyocd")

    assert result["status"] == "ok"
    assert session.config.probe.target == "stm32l496vetx"
    assert result["target_match"]["matched_target"] == "stm32l496vetx"
    assert result["target_patch"]["patch_applied"] is True


def test_configure_probe_normalizes_py32_alias_and_applies_patch() -> None:
    session = SessionState()

    result = configure_probe(session, target="PY32F030X8", backend="CMSIS-DAP")

    assert result["status"] == "ok"
    assert session.config.probe.backend == "pyocd"
    assert session.config.probe.target == "py32f030x8"
    assert result["target_patch"]["patch_applied"] is True
    assert result["target_patch"]["connect_hints"]["attempts"][0]["frequency"] == 100000


def test_get_target_info_reports_patch_metadata() -> None:
    result = get_target_info("STM32F103C8T6", backend="jlink")

    assert result["status"] == "ok"
    assert result["matched_target"] == "STM32F103C8"
    assert result["patch_applied"] is True


def test_connect_with_config_uses_same_probe_preflight_path() -> None:
    captured: dict[str, object] = {"hints": None}

    class _Probe:
        def set_connect_hints(self, hints):
            captured["hints"] = hints

        def connect(self, *, target, unique_id=None):
            captured["target"] = target
            captured["unique_id"] = unique_id
            return {"status": "ok", "summary": f"Connected to {target}."}

        def get_state(self):
            return "running"

    class _Log:
        def connect(self, port, baudrate=115200):
            return {"status": "ok", "summary": f"log {port} {baudrate}"}

    class _Elf:
        def load(self, path):
            return {"status": "ok", "summary": f"elf {path}"}

    session = SessionState()
    session.probe = _Probe()
    session.log = _Log()
    session.elf = _Elf()
    session.config.probe.backend = "jlink"
    session.config.probe.target = "STM32F103C8T6"
    session.config.probe.unique_id = "240710115"
    session.config.probe.connect_attempts = [
        ConnectAttempt(frequency=100000, connect_mode="under-reset")
    ]
    session.config.log.port = "COM3"
    session.config.elf.path = r"d:\demo\firmware.axf"

    result = connect_with_config(session)

    assert result["status"] == "ok"
    assert result["results"]["probe"]["target_match"]["matched_target"] == "STM32F103C8"
    assert result["results"]["probe"]["target_patch"]["patch_applied"] is True
    assert captured["target"] == "STM32F103C8"
    assert captured["unique_id"] == "240710115"
    assert captured["hints"] == {"attempts": [{"frequency": 100000, "connect_mode": "under-reset"}]}
