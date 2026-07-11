from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..session import SessionState


from .phase3_common import _probe_is_connected


def diagnose_peripheral_stuck(
    session: SessionState,
    peripheral: str,
    symptom: str | None = None,
) -> dict[str, Any]:
    """Diagnose why a peripheral is not working.

    Reads peripheral registers (via SVD) and checks whether the RCC clock
    enable bit for the peripheral is set. These two checks together cover the
    most common root causes of a silent/stuck peripheral.
    """
    if not session.svd.is_loaded:
        return {
            "status": "error",
            "summary": "No SVD file loaded. Call svd_load first.",
        }

    if not _probe_is_connected(session):
        return {
            "status": "error",
            "summary": "Probe not connected. Call probe_connect or connect_with_config first.",
        }

    periph_result = session.svd.read_peripheral_state(peripheral, session.probe)
    if periph_result["status"] != "ok":
        return periph_result

    rcc_notes = _check_rcc_clock(session, peripheral)

    diagnosis = periph_result.get("diagnosis", [])
    errors = periph_result.get("errors", [])
    evidence = diagnosis + rcc_notes

    return {
        "status": "ok",
        "peripheral": periph_result["peripheral"],
        "symptom": symptom,
        "summary": (
            f"Diagnosed {periph_result['peripheral']}: "
            f"{len(diagnosis)} register note(s), {len(rcc_notes)} RCC note(s)."
        ),
        "registers": periph_result.get("registers", []),
        "diagnosis": diagnosis,
        "rcc_notes": rcc_notes,
        "evidence": evidence,
        "errors": errors,
    }


def _check_rcc_clock(session: SessionState, peripheral_name: str) -> list[str]:
    """Search SVD RCC registers for the clock-enable bit of *peripheral_name*."""
    notes: list[str] = []

    rcc = session.svd._peripheral_map.get("RCC")
    if rcc is None:
        return ["RCC not found in SVD -- cannot check clock enable."]

    target = peripheral_name.upper() + "EN"
    for reg in rcc.registers or []:
        for field in reg.fields or []:
            if field.name.upper() != target:
                continue
            addr = rcc.base_address + reg.address_offset
            try:
                raw = session.probe.read_memory(addr, 4)
                value = int.from_bytes(raw, "little")
                mask = (1 << field.bit_width) - 1
                enabled = (value >> field.bit_offset) & mask
                if enabled:
                    notes.append(f"RCC clock enabled: {reg.name}.{field.name}=1")
                else:
                    notes.append(
                        f"RCC clock NOT enabled: {reg.name}.{field.name}=0 -- "
                        f"call HAL_RCC_{peripheral_name.upper()}CLK_ENABLE() "
                        f"before initializing the peripheral."
                    )
            except Exception as exc:
                notes.append(f"Failed to read RCC register {reg.name}: {exc}")
            return notes

    notes.append(
        f"No clock-enable bit found for '{peripheral_name}' in RCC registers "
        f"(searched for field '{target}')."
    )
    return notes
