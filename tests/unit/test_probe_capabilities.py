from __future__ import annotations

from types import SimpleNamespace

from McuBuddy.backends.probe.base import ProbeCapability, probe_supports
from McuBuddy.backends.probe.jlink_backend import JLinkProbeBackend
from McuBuddy.backends.probe.pyocd_backend import PyOcdProbeBackend
from McuBuddy.tools.probe import read_cycle_counter


def test_backends_declare_required_core_capabilities() -> None:
    required = {
        ProbeCapability.CORE_CONTROL,
        ProbeCapability.CORE_REGISTERS,
        ProbeCapability.FAULT_REGISTERS,
        ProbeCapability.MEMORY_READ,
        ProbeCapability.MEMORY_WRITE,
        ProbeCapability.BREAKPOINTS,
        ProbeCapability.FLASH,
    }

    assert required <= PyOcdProbeBackend().capabilities
    assert required <= JLinkProbeBackend().capabilities


def test_jlink_declares_trace_capabilities_that_pyocd_does_not() -> None:
    jlink = JLinkProbeBackend().capabilities
    pyocd = PyOcdProbeBackend().capabilities

    assert ProbeCapability.RTT_READ in jlink
    assert ProbeCapability.DWT_CYCLE_COUNTER in jlink
    assert ProbeCapability.SWO in jlink
    assert ProbeCapability.ITM_TRACE in jlink
    assert ProbeCapability.RTT_READ not in pyocd
    assert ProbeCapability.DWT_CYCLE_COUNTER not in pyocd


def test_explicit_capabilities_override_method_presence() -> None:
    probe = SimpleNamespace(
        capabilities=frozenset(),
        read_cycle_counter=lambda: {"status": "ok"},
    )

    assert probe_supports(probe, ProbeCapability.DWT_CYCLE_COUNTER) is False


def test_legacy_test_double_can_fall_back_to_method_presence() -> None:
    probe = SimpleNamespace(read_cycle_counter=lambda: {"status": "ok"})

    assert probe_supports(probe, ProbeCapability.DWT_CYCLE_COUNTER) is True


def test_tool_rejects_explicitly_unsupported_capability_without_calling_backend() -> None:
    calls: list[str] = []
    probe = SimpleNamespace(
        capabilities=frozenset(),
        read_cycle_counter=lambda: calls.append("called"),
    )

    result = read_cycle_counter(SimpleNamespace(probe=probe))

    assert result["status"] == "error"
    assert "does not support" in result["summary"]
    assert calls == []
