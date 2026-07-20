from __future__ import annotations

from ...backends.probe.base import ProbeCapability, probe_supports
from ...session import SessionState
from ...tool_safety import require_tool_confirmation


def set_watchpoint(
    session: SessionState,
    address: int,
    size: int = 4,
    watch_type: str = "write",
    confirm: bool = False,
) -> dict:
    if blocked := require_tool_confirmation("probe_set_watchpoint", confirm):
        return blocked
    return session.probe.set_watchpoint(address, size, watch_type)


def remove_watchpoint(session: SessionState, address: int, confirm: bool = False) -> dict:
    if blocked := require_tool_confirmation("probe_remove_watchpoint", confirm):
        return blocked
    return session.probe.remove_watchpoint(address)


def clear_all_watchpoints(session: SessionState, confirm: bool = False) -> dict:
    if blocked := require_tool_confirmation("probe_clear_all_watchpoints", confirm):
        return blocked
    return session.probe.clear_all_watchpoints()


def read_fpu_registers(session: SessionState) -> dict:
    if not probe_supports(session.probe, ProbeCapability.FPU_REGISTERS):
        return {
            "status": "error",
            "summary": "Active probe backend does not support FPU register reads.",
        }
    try:
        values = session.probe.read_fpu_registers()
    except NotImplementedError:
        return {
            "status": "error",
            "summary": "Active probe backend does not support FPU register reads.",
        }
    return {
        "status": "ok",
        "summary": "Read FPU registers.",
        "registers": {
            name: hex(value) if isinstance(value, int) else value for name, value in values.items()
        },
    }


def read_cycle_counter(session: SessionState, confirm: bool = False) -> dict:
    if not probe_supports(session.probe, ProbeCapability.DWT_CYCLE_COUNTER):
        return {
            "status": "error",
            "summary": "Active probe backend does not support DWT cycle counter reads.",
        }
    if blocked := require_tool_confirmation("read_cycle_counter", confirm):
        return blocked
    try:
        return session.probe.read_cycle_counter()
    except NotImplementedError:
        return {
            "status": "error",
            "summary": "Active probe backend does not support DWT cycle counter reads.",
        }
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }


def read_swo_log(
    session: SessionState,
    cpu_speed_hz: int,
    swo_speed_hz: int,
    max_bytes: int = 1024,
    port_mask: int = 0x01,
    confirm: bool = False,
) -> dict:
    if not probe_supports(session.probe, ProbeCapability.SWO):
        return {
            "status": "error",
            "summary": "Active probe backend does not support SWO log reads.",
        }
    if blocked := require_tool_confirmation("read_swo_log", confirm):
        return blocked
    try:
        return session.probe.read_swo_log(
            cpu_speed_hz=cpu_speed_hz,
            swo_speed_hz=swo_speed_hz,
            max_bytes=max_bytes,
            port_mask=port_mask,
        )
    except NotImplementedError:
        return {
            "status": "error",
            "summary": "Active probe backend does not support SWO log reads.",
        }
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }


def read_itm_trace(
    session: SessionState,
    cpu_speed_hz: int,
    swo_speed_hz: int,
    stimulus_port: int = 0,
    max_bytes: int = 1024,
    port_mask: int | None = None,
) -> dict:
    if not probe_supports(session.probe, ProbeCapability.ITM_TRACE):
        return {
            "status": "error",
            "summary": "Active probe backend does not support ITM trace reads.",
        }
    try:
        return session.probe.read_itm_trace(
            cpu_speed_hz=cpu_speed_hz,
            swo_speed_hz=swo_speed_hz,
            stimulus_port=stimulus_port,
            max_bytes=max_bytes,
            port_mask=port_mask,
        )
    except NotImplementedError:
        return {
            "status": "error",
            "summary": "Active probe backend does not support ITM trace reads.",
        }
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }


_MPU_TYPE = 0xE000ED90
_MPU_CTRL = 0xE000ED94
_MPU_RNR = 0xE000ED98
_MPU_RBAR = 0xE000ED9C
_MPU_RASR = 0xE000EDA0

_AP_DESC = {
    0b000: "privileged_no_access_unprivileged_no_access",
    0b001: "privileged_rw_unprivileged_no_access",
    0b010: "privileged_rw_unprivileged_ro",
    0b011: "privileged_rw_unprivileged_rw",
    0b100: "reserved",
    0b101: "privileged_ro_unprivileged_no_access",
    0b110: "privileged_ro_unprivileged_ro",
    0b111: "reserved",
}


def read_mpu_regions(session: SessionState, confirm: bool = False) -> dict:
    if blocked := require_tool_confirmation("probe_read_mpu_regions", confirm):
        return blocked
    mpu_type = int.from_bytes(session.probe.read_memory(_MPU_TYPE, 4), "little")
    mpu_ctrl = int.from_bytes(session.probe.read_memory(_MPU_CTRL, 4), "little")
    dregion = (mpu_type >> 8) & 0xFF
    regions: list[dict[str, int | bool | str]] = []

    for index in range(dregion):
        session.probe.write_memory(_MPU_RNR, index.to_bytes(4, "little"))
        rbar = int.from_bytes(session.probe.read_memory(_MPU_RBAR, 4), "little")
        rasr = int.from_bytes(session.probe.read_memory(_MPU_RASR, 4), "little")
        region_enable = bool(rasr & 0x1)
        size_field = (rasr >> 1) & 0x1F
        srd = (rasr >> 8) & 0xFF
        ap = (rasr >> 24) & 0x7
        xn = bool((rasr >> 28) & 0x1)
        size_bytes = (1 << (size_field + 1)) if size_field >= 4 else 0
        base_addr = rbar & ~0x1F
        regions.append(
            {
                "index": index,
                "enabled": region_enable,
                "base_address": hex(base_addr),
                "rbar": hex(rbar),
                "rasr": hex(rasr),
                "size_field": size_field,
                "size_bytes": size_bytes,
                "subregion_disable_mask": hex(srd),
                "access_permission_bits": ap,
                "access_permission": _AP_DESC.get(ap, "unknown"),
                "execute_never": xn,
            }
        )

    return {
        "status": "ok",
        "summary": f"Read MPU configuration with {dregion} region slot(s).",
        "mpu": {
            "type": hex(mpu_type),
            "control": hex(mpu_ctrl),
            "enabled": bool(mpu_ctrl & 0x1),
            "privdefena": bool((mpu_ctrl >> 2) & 0x1),
            "dregion": dregion,
        },
        "regions": regions,
    }
