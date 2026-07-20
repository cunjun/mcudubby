from __future__ import annotations

from types import SimpleNamespace

import McuBubby.tools.diagnose_router as diagnose_router
from McuBubby.tools.diagnose_router import DIAGNOSE_ROUTES


def test_diagnose_routes_are_data_driven() -> None:
    profiles = {route.profile for route in DIAGNOSE_ROUTES}

    assert {
        "hardfault",
        "stack-overflow",
        "memory-corruption",
        "interrupt",
        "clock",
        "peripheral",
        "rtos-stall",
        "startup",
    }.issubset(profiles)
    assert all(route.name.startswith("diagnose_") for route in DIAGNOSE_ROUTES)
    assert all(route.workflow_stage.endswith("-triage") for route in DIAGNOSE_ROUTES)


def test_diagnose_routes_hardfault(monkeypatch) -> None:
    session = SimpleNamespace()
    monkeypatch.setattr(
        diagnose_router,
        "diagnose_hardfault",
        lambda session, **kwargs: {"status": "ok", "summary": "hardfault details"},
    )

    result = diagnose_router.diagnose(session, symptom="Board crashed into HardFault")

    assert result["status"] == "ok"
    assert result["diagnose_route"] == "diagnose_hardfault"
    assert result["diagnose_profile"] == "hardfault"
    assert result["workflow_stage"] == "fault-triage"
    assert "dwarf_backtrace" in result["recommended_next_tools"]
    assert result["summary"].startswith("Routed to hardfault diagnosis:")


def test_diagnose_routes_peripheral_and_infers_name(monkeypatch) -> None:
    session = SimpleNamespace()
    calls: list[tuple[str, str | None]] = []

    def _fake_peripheral(session, peripheral, symptom=None):
        calls.append((peripheral, symptom))
        return {"status": "ok", "summary": "peripheral details"}

    monkeypatch.setattr(diagnose_router, "diagnose_peripheral_stuck", _fake_peripheral)

    result = diagnose_router.diagnose(session, symptom="USART2 no output from TX pin")

    assert result["status"] == "ok"
    assert result["diagnose_route"] == "diagnose_peripheral_stuck"
    assert result["diagnose_profile"] == "peripheral"
    assert result["peripheral"] == "USART2"
    assert "GPIO mux configuration" in result["evidence_focus"]
    assert calls == [("USART2", "USART2 no output from TX pin")]


def test_diagnose_routes_clock_issue(monkeypatch) -> None:
    session = SimpleNamespace()
    monkeypatch.setattr(
        diagnose_router,
        "diagnose_clock_issue",
        lambda session: {"status": "ok", "summary": "clock details"},
    )

    result = diagnose_router.diagnose(session, symptom="PLL clock switch is stuck")

    assert result["status"] == "ok"
    assert result["diagnose_route"] == "diagnose_clock_issue"
    assert result["diagnose_profile"] == "clock"
    assert result["workflow_stage"] == "clock-triage"


def test_diagnose_falls_back_to_startup(monkeypatch) -> None:
    session = SimpleNamespace()
    monkeypatch.setattr(
        diagnose_router,
        "diagnose_startup_failure",
        lambda session, **kwargs: {"status": "ok", "summary": "startup details"},
    )

    result = diagnose_router.diagnose(session, symptom="Board does not boot")

    assert result["status"] == "ok"
    assert result["diagnose_route"] == "diagnose_startup_failure"
    assert result["diagnose_profile"] == "startup"
    assert result["workflow_stage"] == "startup-triage"


def test_diagnose_requires_non_empty_symptom() -> None:
    session = SimpleNamespace()

    result = diagnose_router.diagnose(session, symptom="  ")

    assert result["status"] == "error"


def test_diagnose_marks_rtos_stall_profile(monkeypatch) -> None:
    session = SimpleNamespace()
    monkeypatch.setattr(
        diagnose_router,
        "diagnose_startup_failure",
        lambda session, **kwargs: {"status": "ok", "summary": "startup details"},
    )

    result = diagnose_router.diagnose(session, symptom="FreeRTOS task stuck waiting forever")

    assert result["status"] == "ok"
    assert result["diagnose_route"] == "diagnose_startup_failure"
    assert result["diagnose_profile"] == "rtos-stall"
    assert result["workflow_stage"] == "rtos-triage"
    assert result["recommended_next_tools"][:2] == ["list_rtos_tasks", "rtos_task_context"]
