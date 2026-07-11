from __future__ import annotations

from dataclasses import dataclass

from .diagnose import diagnose_hardfault, diagnose_startup_failure
from .phase3 import (
    diagnose_clock_issue,
    diagnose_interrupt_issue,
    diagnose_peripheral_stuck,
    diagnose_stack_overflow,
)
from .probe import diagnose_memory_corruption
from ..session import SessionState


@dataclass(frozen=True)
class DiagnoseRoute:
    name: str
    label: str
    profile: str
    reason: str
    workflow_stage: str
    patterns: tuple[str, ...]
    requires_peripheral: bool = False
    default_route: bool = False


DIAGNOSE_ROUTES: tuple[DiagnoseRoute, ...] = (
    DiagnoseRoute(
        name="diagnose_hardfault",
        label="Routed to hardfault diagnosis",
        profile="hardfault",
        reason="Symptom mentions a crash or HardFault-class failure.",
        workflow_stage="fault-triage",
        patterns=("hardfault", "hard fault", "fault handler", "crash", "crashed"),
    ),
    DiagnoseRoute(
        name="diagnose_stack_overflow",
        label="Routed to stack-overflow diagnosis",
        profile="stack-overflow",
        reason="Symptom explicitly mentions stack overflow or stack corruption.",
        workflow_stage="memory-triage",
        patterns=("stack overflow", "stack smashed", "stack crash", "overflowed stack"),
    ),
    DiagnoseRoute(
        name="diagnose_memory_corruption",
        label="Routed to memory-corruption diagnosis",
        profile="memory-corruption",
        reason="Symptom suggests corruption of stack, heap, or guard/canary state.",
        workflow_stage="memory-triage",
        patterns=(
            "memory corruption",
            "heap corruption",
            "corruption",
            "heap overwrite",
            "stack canary",
        ),
    ),
    DiagnoseRoute(
        name="diagnose_interrupt_issue",
        label="Routed to interrupt diagnosis",
        profile="interrupt",
        reason="Symptom points to IRQ, ISR, or NVIC behavior.",
        workflow_stage="interrupt-triage",
        patterns=("interrupt", "irq", "nvic", "isr", "pending irq"),
    ),
    DiagnoseRoute(
        name="diagnose_clock_issue",
        label="Routed to clock diagnosis",
        profile="clock",
        reason="Symptom mentions system clock, PLL, or oscillator selection.",
        workflow_stage="clock-triage",
        patterns=("clock", "pll", "hse", "hsi", "msi", "sws", "system clock"),
    ),
    DiagnoseRoute(
        name="diagnose_peripheral_stuck",
        label="Routed to peripheral diagnosis",
        profile="peripheral",
        reason="Symptom references a peripheral, data path, or missing pin-level output.",
        workflow_stage="peripheral-triage",
        patterns=("uart", "spi", "i2c", "gpio", "peripheral", "tx pin", "rx pin", "no output"),
        requires_peripheral=True,
    ),
    DiagnoseRoute(
        name="diagnose_startup_failure",
        label="Routed to startup diagnosis",
        profile="rtos-stall",
        reason="No dedicated RTOS stall diagnoser exists yet, so startup/stop-state analysis is used as the broad evidence pass.",
        workflow_stage="rtos-triage",
        patterns=("task stuck", "task blocked", "rtos", "deadlock", "scheduler", "thread stuck"),
    ),
    DiagnoseRoute(
        name="diagnose_startup_failure",
        label="Routed to startup diagnosis",
        profile="startup",
        reason="No narrower symptom class matched, so startup/state triage is the default broad diagnostic path.",
        workflow_stage="startup-triage",
        patterns=(),
        default_route=True,
    ),
)


def diagnose(
    session: SessionState,
    symptom: str,
    peripheral: str | None = None,
    suspected_stage: str | None = None,
    include_logs: bool = True,
    auto_halt: bool = True,
    stack_canary: int = 0xCCCCCCCC,
) -> dict:
    normalized = (symptom or "").strip().lower()
    if not normalized:
        return {
            "status": "error",
            "summary": "symptom must not be empty.",
        }

    route = _select_route(normalized=normalized, peripheral=peripheral)

    if route["name"] == "diagnose_hardfault":
        result = diagnose_hardfault(
            session,
            auto_halt=auto_halt,
            include_logs=include_logs,
            suspected_stage=suspected_stage,
        )
    elif route["name"] == "diagnose_startup_failure":
        result = diagnose_startup_failure(
            session,
            auto_halt=auto_halt,
            include_logs=include_logs,
            suspected_stage=suspected_stage,
        )
    elif route["name"] == "diagnose_peripheral_stuck":
        result = diagnose_peripheral_stuck(
            session,
            peripheral=peripheral or route["inferred_peripheral"] or "unknown",
            symptom=symptom,
        )
    elif route["name"] == "diagnose_stack_overflow":
        result = diagnose_stack_overflow(session)
    elif route["name"] == "diagnose_interrupt_issue":
        result = diagnose_interrupt_issue(session)
    elif route["name"] == "diagnose_clock_issue":
        result = diagnose_clock_issue(session)
    elif route["name"] == "diagnose_memory_corruption":
        result = diagnose_memory_corruption(session, stack_canary=stack_canary)
    else:
        return {
            "status": "error",
            "summary": f"Unsupported diagnose route '{route['name']}'.",
        }

    if not isinstance(result, dict):
        return {
            "status": "error",
            "summary": f"Diagnose route '{route['name']}' returned a non-dict result.",
        }

    result = dict(result)
    result["symptom"] = symptom
    result["diagnose_route"] = route["name"]
    result["diagnose_profile"] = route["profile"]
    result["route_reason"] = route["reason"]
    result["recommended_next_tools"] = _recommended_next_tools(
        route, inferred_peripheral=route["inferred_peripheral"]
    )
    result["evidence_focus"] = _evidence_focus(
        route, inferred_peripheral=route["inferred_peripheral"]
    )
    result["workflow_stage"] = route["workflow_stage"]
    if route["inferred_peripheral"] is not None and "peripheral" not in result:
        result["peripheral"] = route["inferred_peripheral"]
    if result.get("status") == "ok":
        result["summary"] = f"{route['label']}: {result['summary']}"
    return result


def _select_route(normalized: str, peripheral: str | None) -> dict[str, str | None]:
    inferred_peripheral = peripheral or _infer_peripheral_name(normalized)
    default_route = DIAGNOSE_ROUTES[-1]
    for route in DIAGNOSE_ROUTES:
        if route.default_route:
            default_route = route
            continue
        if route.requires_peripheral and inferred_peripheral is not None:
            return _route_to_dict(route, inferred_peripheral)
        if _has_any(normalized, route.patterns):
            return _route_to_dict(route, inferred_peripheral)
    return _route_to_dict(default_route, inferred_peripheral)


def _route_to_dict(route: DiagnoseRoute, inferred_peripheral: str | None) -> dict[str, str | None]:
    return {
        "name": route.name,
        "label": route.label,
        "profile": route.profile,
        "reason": route.reason,
        "workflow_stage": route.workflow_stage,
        "inferred_peripheral": inferred_peripheral,
    }


def _has_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _infer_peripheral_name(text: str) -> str | None:
    tokens = text.replace(",", " ").replace(":", " ").replace("(", " ").replace(")", " ").split()
    for token in tokens:
        upper = token.upper()
        if upper.startswith(("USART", "UART", "SPI", "I2C", "GPIO", "TIM", "ADC", "DAC", "RCC")):
            return upper
    return None


def _recommended_next_tools(
    route: dict[str, str | None], inferred_peripheral: str | None
) -> list[str]:
    profile = route["profile"]
    if profile == "hardfault":
        return ["dwarf_backtrace", "get_locals", "disassemble", "dump_memory"]
    if profile in {"stack-overflow", "memory-corruption"}:
        return ["read_stack_usage", "dump_memory", "read_symbol_value"]
    if profile == "interrupt":
        return ["read_stopped_context", "svd_read_peripheral", "probe_read_registers"]
    if profile == "clock":
        return ["svd_read_peripheral", "read_stopped_context", "dump_memory"]
    if profile == "peripheral":
        tools = ["svd_read_peripheral", "read_stopped_context"]
        if inferred_peripheral is not None:
            tools.insert(0, f"svd_read_peripheral('{inferred_peripheral}')")
        return tools
    if profile == "rtos-stall":
        return ["list_rtos_tasks", "rtos_task_context", "read_stack_usage", "read_rtt_log"]
    return ["read_stopped_context", "elf_addr_to_source", "read_rtt_log"]


def _evidence_focus(route: dict[str, str | None], inferred_peripheral: str | None) -> list[str]:
    profile = route["profile"]
    if profile == "hardfault":
        return ["fault registers", "PC/LR source location", "backtrace frames", "stack snapshot"]
    if profile in {"stack-overflow", "memory-corruption"}:
        return ["stack canary usage", "SP bounds", "heap/stack corruption markers"]
    if profile == "interrupt":
        return ["pending IRQ state", "handler context", "NVIC enable/priority state"]
    if profile == "clock":
        return ["clock source bits", "PLL status", "system clock switch state"]
    if profile == "peripheral":
        if inferred_peripheral is not None:
            return [
                f"{inferred_peripheral} register state",
                "RCC clock gating",
                "GPIO mux configuration",
            ]
        return ["peripheral register state", "RCC clock gating", "GPIO mux configuration"]
    if profile == "rtos-stall":
        return [
            "task states",
            "blocked wait function",
            "RTT progress logs",
            "stack high-water marks",
        ]
    return ["current PC/source location", "recent logs", "fault bits if present"]
