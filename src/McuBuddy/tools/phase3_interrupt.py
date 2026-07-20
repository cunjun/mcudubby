from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..session import SessionState


from .phase3_common import _probe_is_connected


def diagnose_interrupt_issue(session: SessionState) -> dict[str, Any]:
    if not _probe_is_connected(session):
        return {
            "status": "error",
            "summary": "Probe not connected. Call probe_connect or connect_with_config first.",
        }

    try:
        raw = session.probe.read_memory(0xE000ED04, 4)
        icsr = int.from_bytes(raw, "little")
    except Exception as exc:
        return {"status": "error", "summary": f"Failed to read SCB_ICSR (0xE000ED04): {exc}"}

    active_exception_number = icsr & 0x1FF
    pending_exception_number = (icsr >> 12) & 0x1FF
    in_interrupt = active_exception_number != 0

    try:
        enabled_irqs = _collect_nvic_irq_numbers(session, 0xE000E100)
        pending_irqs = _collect_nvic_irq_numbers(session, 0xE000E200)
        active_irqs = _collect_nvic_irq_numbers(session, 0xE000E300)
    except Exception as exc:
        return {"status": "error", "summary": f"Failed to read NVIC state: {exc}"}

    evidence = [
        (
            f"SCB_ICSR active_exception={active_exception_number}, "
            f"pending_exception={pending_exception_number}"
        ),
        f"NVIC enabled IRQs: {len(enabled_irqs)}",
        f"NVIC pending IRQs: {len(pending_irqs)}",
        f"NVIC active IRQs: {len(active_irqs)}",
    ]
    if in_interrupt:
        evidence.append(f"Core is currently servicing exception {active_exception_number}.")
    if pending_exception_number != 0:
        evidence.append(f"Exception {pending_exception_number} is pending in SCB_ICSR.")
    if pending_irqs and not active_irqs:
        evidence.append("One or more IRQs are pending but none are active.")

    suggested_next_steps = [
        "Compare pending_irqs against your expected peripheral IRQ number and confirm the ISR is enabled in startup code.",
        "If an IRQ is pending but not active, inspect masking/priority state such as PRIMASK, BASEPRI, and NVIC priority configuration.",
        "If no IRQs are enabled, verify that NVIC_EnableIRQ() or the vendor HAL equivalent was called.",
    ]

    return {
        "status": "ok",
        "summary": (
            f"Interrupt state captured: {len(enabled_irqs)} enabled IRQs, "
            f"{len(pending_irqs)} pending IRQs, {len(active_irqs)} active IRQs."
        ),
        "current_exception": {
            "active_exception_number": active_exception_number,
            "pending_exception_number": pending_exception_number,
            "in_interrupt": in_interrupt,
        },
        "enabled_irqs": enabled_irqs,
        "pending_irqs": pending_irqs,
        "active_irqs": active_irqs,
        "enabled_count": len(enabled_irqs),
        "evidence": evidence,
        "suggested_next_steps": suggested_next_steps,
    }


def _collect_nvic_irq_numbers(session: SessionState, base_address: int) -> list[int]:
    register_values: list[int] = []
    for register_index in range(8):
        addr = base_address + (register_index * 4)
        raw = session.probe.read_memory(addr, 4)
        register_values.append(int.from_bytes(raw, "little"))

    irq_numbers: list[int] = []
    for irq_number in range(240):
        register_index = irq_number // 32
        bit_index = irq_number % 32
        value = register_values[register_index]
        if (value >> bit_index) & 1:
            irq_numbers.append(irq_number)
    return irq_numbers
