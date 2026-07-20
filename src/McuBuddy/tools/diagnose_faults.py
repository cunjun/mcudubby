from __future__ import annotations


def _classify_fault(fault_registers: dict[str, int]) -> str:
    cfsr = fault_registers.get("cfsr", 0)
    if cfsr & 0x00008200:
        return "precise_data_bus_error"
    if cfsr & 0x00000400:
        return "imprecise_data_bus_error"
    if cfsr & 0x00000001:
        return "instruction_access_violation"
    if cfsr & 0x00000002:
        return "data_access_violation"
    if cfsr & 0x00010000:
        return "usage_fault"
    if fault_registers.get("hfsr", 0) & 0x40000000:
        return "forced_hardfault"
    return "hardfault_handler_entered"


def _describe_fault(fault_class: str) -> str:
    descriptions = {
        "precise_data_bus_error": "A precise data bus fault was reported by CFSR.",
        "imprecise_data_bus_error": "An imprecise data bus fault was reported by CFSR.",
        "instruction_access_violation": "An instruction access violation was reported by CFSR.",
        "data_access_violation": "A data access violation was reported by CFSR.",
        "usage_fault": "A usage fault was reported by CFSR.",
        "forced_hardfault": "A configurable fault escalated into HardFault.",
        "hardfault_handler_entered": "The CPU is currently in HardFault handler.",
    }
    return descriptions[fault_class]


def _infer_stage_from_logs(last_meaningful: str | None) -> str:
    if not last_meaningful:
        return "early boot"

    normalized = last_meaningful.lower()
    if "clock" in normalized:
        return "clock initialization"
    if "uart" in normalized:
        return "uart initialization"
    if "sensor" in normalized:
        return "sensor initialization"
    if "init" in normalized:
        return "initialization"
    return "startup"


def _logs_indicate_startup_success(log_lines: list[str]) -> bool:
    success_markers = (
        "sensor init ok",
        "app loop running",
        "startup complete",
        "boot complete",
    )
    normalized_lines = [line.lower() for line in log_lines]
    return any(marker in line for line in normalized_lines for marker in success_markers)


def _build_fault_notes(
    fault_registers: dict[str, int],
    core: dict[str, int],
    pc_symbol: str | None,
    lr_symbol: str | None,
) -> dict:
    cfsr = fault_registers.get("cfsr", 0)
    notes = {
        "evidence": [],
        "root_causes": [],
        "next_steps": [],
    }

    if cfsr & 0x00000001:
        notes["evidence"].append("CFSR bit 0 indicates an instruction access violation.")
        notes["root_causes"].append(
            {
                "label": "invalid execution target or illegal function entry",
                "confidence": "high",
            }
        )
        notes["root_causes"].append(
            {
                "label": "control flow jumped to an unmapped address during startup",
                "confidence": "medium",
            }
        )
        notes["next_steps"].extend(
            [
                "Resolve the stacked PC/LR values against the ELF symbols.",
                "Verify whether the failing path uses an invalid function pointer or forced bad entry address.",
                "Confirm the startup control flow immediately before the fault site.",
            ]
        )
    elif cfsr & 0x00008200:
        notes["root_causes"].append(
            {
                "label": "invalid pointer dereference during initialization",
                "confidence": "high",
            }
        )
        notes["root_causes"].append(
            {
                "label": "incorrect peripheral register access",
                "confidence": "medium",
            }
        )
        notes["next_steps"].extend(
            [
                "Inspect the last memory access in the failing init path.",
                "Verify all startup handles are initialized before use.",
                "Check register base addresses used around the fault site.",
            ]
        )
    else:
        notes["root_causes"].append(
            {
                "label": "startup-stage fault with incomplete classification",
                "confidence": "medium",
            }
        )
        notes["next_steps"].extend(
            [
                "Inspect the stacked register frame and resolve PC/LR against the ELF.",
                "Compare the fault register values with the Cortex-M fault status definitions.",
            ]
        )

    if pc_symbol == "HardFault_Handler":
        notes["evidence"].append("PC currently resolves to HardFault_Handler.")
    if lr_symbol:
        notes["evidence"].append(f"LR resolves to {lr_symbol}.")
    if core.get("pc") == 0xFFFFFFFF:
        notes["evidence"].append(
            "PC contains 0xFFFFFFFF, which strongly suggests an invalid execution target."
        )

    return notes
