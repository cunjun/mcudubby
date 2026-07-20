from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..session import SessionState


from .phase3_common import _probe_is_connected


def diagnose_clock_issue(session: SessionState) -> dict[str, Any]:
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

    rcc = session.svd._peripheral_map.get("RCC")
    if rcc is None:
        return {
            "status": "error",
            "summary": "RCC not found in SVD.",
        }

    reg_map = {reg.name.upper(): reg for reg in (rcc.registers or []) if getattr(reg, "name", None)}
    required_registers = ("CR", "CFGR", "PLLCFGR")
    register_values: dict[str, int | None] = {}
    for reg_name in required_registers:
        reg = reg_map.get(reg_name)
        if reg is None:
            register_values[reg_name] = None
            continue
        addr = rcc.base_address + reg.address_offset
        try:
            raw = session.probe.read_memory(addr, 4)
            register_values[reg_name] = int.from_bytes(raw, "little")
        except Exception as exc:
            return {
                "status": "error",
                "summary": f"Failed to read RCC.{reg_name} at {hex(addr)}: {exc}",
            }

    cr_fields = _extract_register_fields(reg_map.get("CR"), register_values.get("CR"))
    cfgr_fields = _extract_register_fields(reg_map.get("CFGR"), register_values.get("CFGR"))
    pllcfgr_fields = _extract_register_fields(
        reg_map.get("PLLCFGR"), register_values.get("PLLCFGR")
    )

    sw = cfgr_fields.get("SW")
    sws = cfgr_fields.get("SWS")
    hsi_enabled = _field_enabled(cr_fields, "HSION")
    hsi_ready = _field_enabled(cr_fields, "HSIRDY")
    hse_enabled = _field_enabled(cr_fields, "HSEON")
    hse_ready = _field_enabled(cr_fields, "HSERDY")
    pll_enabled = _field_enabled(cr_fields, "PLLON")
    pll_ready = _field_enabled(cr_fields, "PLLRDY")
    pll_source_value = pllcfgr_fields.get("PLLSRC")

    requested_clock = _decode_system_clock_source(sw)
    actual_clock = _decode_system_clock_source(sws)
    pll_source = _decode_pll_source(pll_source_value)
    mismatch = sw is not None and sws is not None and sw != sws

    evidence: list[str] = []
    suggested_next_steps: list[str] = []

    if mismatch:
        evidence.append(
            f"Clock switch not complete: CFGR.SW={sw} ({requested_clock}), CFGR.SWS={sws} ({actual_clock})."
        )
        suggested_next_steps.append(
            "Wait for CFGR.SWS to match CFGR.SW before assuming the system clock source changed."
        )
    if pll_enabled and pll_ready is False:
        evidence.append("PLL is enabled but not locked yet: CR.PLLON=1, CR.PLLRDY=0.")
        suggested_next_steps.append(
            "Check PLL input clock, divisors, and startup delay; the PLL is not reporting ready."
        )
    if hse_enabled and hse_ready is False:
        evidence.append("HSE is enabled but not ready: CR.HSEON=1, CR.HSERDY=0.")
        suggested_next_steps.append(
            "Verify the external crystal/clock source and board load network; HSE is not stabilizing."
        )
    if not evidence:
        evidence.append(
            f"Clock tree appears stable: requested={requested_clock}, actual={actual_clock}, PLL source={pll_source}."
        )
        suggested_next_steps.append(
            "If timing is still wrong, inspect bus prescalers and peripheral-specific clock mux settings."
        )

    raw_registers = {
        name: ("unavailable" if value is None else hex(value))
        for name, value in register_values.items()
    }

    return {
        "status": "ok",
        "summary": (
            f"Clock state captured: requested={requested_clock}, actual={actual_clock}, "
            f"PLL={('on' if pll_enabled else 'off' if pll_enabled is not None else 'unknown')}."
        ),
        "clock_source": {
            "requested": requested_clock,
            "actual": actual_clock,
            "mismatch": mismatch,
        },
        "hsi": {"enabled": hsi_enabled, "ready": hsi_ready},
        "hse": {"enabled": hse_enabled, "ready": hse_ready},
        "pll": {
            "enabled": pll_enabled,
            "ready": pll_ready,
            "source": pll_source,
            "locked": bool(pll_enabled and pll_ready),
        },
        "raw_registers": raw_registers,
        "evidence": evidence,
        "suggested_next_steps": suggested_next_steps,
    }


def _extract_register_fields(register: Any | None, value: int | None) -> dict[str, int]:
    if register is None or value is None:
        return {}

    decoded: dict[str, int] = {}
    for field in register.fields or []:
        mask = (1 << field.bit_width) - 1
        decoded[field.name.upper()] = (value >> field.bit_offset) & mask
    return decoded


def _field_enabled(fields: dict[str, int], name: str) -> bool | None:
    value = fields.get(name)
    return None if value is None else bool(value)


def _decode_system_clock_source(value: int | None) -> str:
    # STM32L4 CFGR SW/SWS encoding: 0=MSI, 1=HSI16, 2=HSE, 3=PLL
    mapping = {
        0: "MSI",
        1: "HSI16",
        2: "HSE",
        3: "PLL",
    }
    if value is None:
        return "Unknown"
    return mapping.get(value, f"Unknown({value})")


def _decode_pll_source(value: int | None) -> str:
    # STM32L4 PLLCFGR PLLSRC encoding: 0=None, 1=MSI, 2=HSI16, 3=HSE
    mapping = {
        0: "None",
        1: "MSI",
        2: "HSI16",
        3: "HSE",
    }
    if value is None:
        return "Unknown"
    return mapping.get(value, f"Unknown({value})")
