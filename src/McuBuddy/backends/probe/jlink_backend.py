from __future__ import annotations

import os
import struct
import time
from pathlib import Path
from typing import Any

from ...errors import BackendUnavailableError
from .base import ProbeBackend, ProbeCapability

try:  # pragma: no cover - import availability depends on local environment
    import pylink
    from pylink import library as pylink_library
except ImportError:  # pragma: no cover
    pylink = None
    pylink_library = None


class JLinkProbeBackend(ProbeBackend):
    """Minimal J-Link probe backend built on top of pylink-square."""

    CAPABILITIES = ProbeBackend.CAPABILITIES | {
        ProbeCapability.WATCHPOINTS,
        ProbeCapability.FPU_REGISTERS,
        ProbeCapability.FLASH,
        ProbeCapability.RTT_READ,
        ProbeCapability.DWT_CYCLE_COUNTER,
        ProbeCapability.SWO,
        ProbeCapability.ITM_TRACE,
        ProbeCapability.CONNECT_HINTS,
    }

    _DEMCR = 0xE000EDFC
    _DWT_CTRL = 0xE0001000
    _DWT_CYCCNT = 0xE0001004
    _DEMCR_TRCENA = 1 << 24
    _DWT_CTRL_CYCCNTENA = 1 << 0

    _REGISTER_ALIASES = {
        "pc": "R15 (PC)",
        "sp": "R13 (SP)",
        "lr": "R14",
        "xpsr": "XPSR",
    }

    def __init__(self, dll_path: str | None = None) -> None:
        self._dll_path = dll_path
        self._library = None
        self._jlink = None
        self._connected = False
        self._target = None
        self._breakpoints: set[int] = set()
        self._watchpoints: dict[
            int, tuple[int, int, str]
        ] = {}  # addr -> (size, handle, watch_type)
        self._rtt_started = False
        self._connect_hints: dict[str, Any] = {}
        self._swo_config: tuple[int, int, int] | None = None

    def set_connect_hints(self, hints: dict[str, Any]) -> None:
        self._connect_hints = dict(hints)

    @classmethod
    def enumerate_probes(cls) -> list[dict[str, Any]]:
        if pylink is None or pylink_library is None:
            return []
        try:
            library = cls._create_library()
            jlink = pylink.JLink(lib=library)
            try:
                emulators = jlink.connected_emulators()
            finally:
                try:
                    jlink.close()
                except Exception:
                    pass
        except Exception:
            return []

        probes = []
        for emulator in emulators:
            product = getattr(emulator, "acProduct", "J-Link")
            if isinstance(product, bytes):
                product = product.decode("utf-8", errors="replace").rstrip("\x00")
            probes.append(
                {
                    "unique_id": str(getattr(emulator, "SerialNumber", "")),
                    "description": f"J-Link {getattr(emulator, 'SerialNumber', '')}".strip(),
                    "product": product,
                }
            )
        return probes

    def connect(self, target: str, unique_id: str | None = None) -> dict[str, Any]:
        self._require_library()
        if self._jlink is not None:
            self.disconnect()
        jlink = pylink.JLink(lib=self._get_library())
        if unique_id:
            jlink.open(serial_no=int(unique_id))
        else:
            jlink.open()

        jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
        attempted_speeds: list[int | str] = []
        last_error: Exception | None = None
        speeds = self._connect_hints.get("speeds", [4000, 1000, 400, "auto"])
        for speed in speeds:
            attempted_speeds.append(speed)
            try:
                jlink.connect(target, speed=speed)
                self._jlink = jlink
                self._connected = True
                self._target = target
                return {
                    "status": "ok",
                    "summary": f"Connected to J-Link target {target}.",
                    "backend": "jlink",
                    "target": target,
                    "unique_id": unique_id,
                    "dll_path": self._dll_path,
                    "speed_khz": speed,
                    "attempted_speeds": attempted_speeds,
                }
            except Exception as exc:
                last_error = exc

        try:
            jlink.close()
        except Exception:
            pass
        raise BackendUnavailableError(
            f"J-Link connect failed for target {target} after speeds {attempted_speeds}: {last_error}"
        )

    def disconnect(self) -> dict[str, Any]:
        if self._jlink is not None:
            try:
                if self._rtt_started:
                    try:
                        self._jlink.rtt_stop()
                    except Exception:
                        pass
                self._jlink.close()
            finally:
                self._jlink = None
                self._connected = False
                self._breakpoints.clear()
                self._watchpoints.clear()
                self._rtt_started = False
                self._swo_config = None
        return {"status": "ok", "summary": "Disconnected J-Link probe."}

    def halt(self) -> dict[str, Any]:
        self._require_connected()
        self._jlink.halt()
        return {"status": "ok", "summary": "Target halted."}

    def resume(self) -> dict[str, Any]:
        self._require_connected()
        self._run_target()
        return {"status": "ok", "summary": "Target resumed.", "state": self.get_state()}

    def reset(self, halt: bool = False) -> dict[str, Any]:
        self._require_connected()
        self._jlink.reset(halt=halt)
        return {
            "status": "ok",
            "summary": f"Target reset ({'halt' if halt else 'run'}).",
            "state": self.get_state(),
        }

    def set_breakpoint(self, address: int) -> dict[str, Any]:
        self._require_connected()
        normalized = address & ~1
        self._jlink.breakpoint_set(normalized)
        self._breakpoints.add(normalized)
        return {
            "status": "ok",
            "summary": f"Breakpoint set at {hex(normalized)}.",
            "address": hex(normalized),
        }

    def clear_breakpoint(self, address: int) -> dict[str, Any]:
        self._require_connected()
        normalized = address & ~1
        self._jlink.breakpoint_clear(normalized)
        self._breakpoints.discard(normalized)
        return {
            "status": "ok",
            "summary": f"Breakpoint cleared at {hex(normalized)}.",
            "address": hex(normalized),
        }

    def clear_all_breakpoints(self) -> dict[str, Any]:
        self._require_connected()
        self._jlink.breakpoint_clear_all()
        cleared = len(self._breakpoints)
        self._breakpoints.clear()
        return {
            "status": "ok",
            "summary": f"Cleared {cleared} breakpoint(s).",
            "cleared_count": cleared,
        }

    def continue_target(
        self,
        timeout_seconds: float = 5.0,
        poll_interval_seconds: float = 0.05,
    ) -> dict[str, Any]:
        self._require_connected()
        self._run_target()

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self._jlink.halted():
                pc = self._read_register("pc")
                return {
                    "status": "ok",
                    "summary": "Target stopped after continue.",
                    "pc": hex(pc),
                    "stop_reason": self._infer_stop_reason(pc),
                    "state": self.get_state(),
                }
            time.sleep(poll_interval_seconds)

        # J-Link cannot read core registers while the CPU is still running.
        # Halt before sampling PC so timeout results are still useful to higher-level tools.
        self._jlink.halt()
        pc = self._read_register("pc")
        return {
            "status": "ok",
            "summary": f"Timeout expired; target was halted at {hex(pc)} for inspection.",
            "pc": hex(pc),
            "stop_reason": "timeout",
            "state": self.get_state(),
        }

    def get_state(self) -> str:
        self._require_connected()
        return "halted" if self._jlink.halted() else "running"

    def read_core_registers(self) -> dict[str, int]:
        self._require_connected()
        registers = {}
        for name in (
            "R0",
            "R1",
            "R2",
            "R3",
            "R4",
            "R5",
            "R6",
            "R7",
            "R8",
            "R9",
            "R10",
            "R11",
            "R12",
        ):
            registers[name.lower()] = self._jlink.register_read(name)
        registers["sp"] = self._read_register("sp")
        registers["lr"] = self._read_register("lr")
        registers["pc"] = self._read_register("pc")
        registers["xpsr"] = self._read_register("xpsr")
        return registers

    def read_fault_registers(self) -> dict[str, int]:
        self._require_connected()
        addresses = {
            "cfsr": 0xE000ED28,
            "hfsr": 0xE000ED2C,
            "mmfar": 0xE000ED34,
            "bfar": 0xE000ED38,
            "shcsr": 0xE000ED24,
        }
        return {
            name: self._jlink.memory_read32(address, 1)[0] for name, address in addresses.items()
        }

    def read_memory(self, address: int, size: int) -> bytes:
        self._require_connected()
        return bytes(self._jlink.memory_read8(address, size))

    def write_memory(self, address: int, data: bytes) -> None:
        self._require_connected()
        self._jlink.memory_write8(address, list(data))

    def step(self) -> dict[str, Any]:
        self._require_connected()
        self._jlink.step()
        pc = self._read_register("pc")
        return {
            "status": "ok",
            "summary": "Executed one instruction.",
            "pc": hex(pc),
            "state": self.get_state(),
        }

    # -- Watchpoints --

    def set_watchpoint(self, address: int, size: int, watch_type: str) -> dict[str, Any]:
        self._require_connected()
        read_flag = watch_type in ("read", "read_write")
        write_flag = watch_type in ("write", "read_write")
        if not read_flag and not write_flag:
            raise ValueError(f"Invalid watch_type '{watch_type}'. Use: read, write, read_write")
        # pylink access_size is in bits (8/16/32), size param is in bytes
        access_size_bits = size * 8 if size in (1, 2, 4) else None
        handle = self._jlink.watchpoint_set(
            address,
            addr_mask=0,
            data=0,
            data_mask=0,
            access_size=access_size_bits,
            read=read_flag,
            write=write_flag,
        )
        self._watchpoints[int(address)] = (size, handle, watch_type)
        return {
            "status": "ok",
            "summary": f"Watchpoint set at {hex(address)}, size={size}, type={watch_type}.",
            "address": hex(address),
            "size": size,
            "watch_type": watch_type,
        }

    def remove_watchpoint(self, address: int) -> dict[str, Any]:
        self._require_connected()
        entry = self._watchpoints.get(int(address))
        if entry is None:
            raise BackendUnavailableError(f"watchpoint at {hex(address)} is not set")
        _size, handle, _watch_type = entry
        self._jlink.watchpoint_clear(handle)
        self._watchpoints.pop(int(address), None)
        return {
            "status": "ok",
            "summary": f"Watchpoint removed at {hex(address)}.",
            "address": hex(address),
        }

    def clear_all_watchpoints(self) -> dict[str, Any]:
        self._require_connected()
        cleared = len(self._watchpoints)
        self._jlink.watchpoint_clear_all()
        self._watchpoints.clear()
        return {
            "status": "ok",
            "summary": f"Cleared {cleared} watchpoint(s).",
            "cleared_count": cleared,
        }

    # -- FPU Registers --

    def read_fpu_registers(self) -> dict[str, Any]:
        self._require_connected()
        result: dict[str, Any] = {}
        for index in range(32):
            name = f"S{index}"
            try:
                raw = self._jlink.register_read(name)
                result[name.lower()] = struct.unpack("<f", struct.pack("<I", raw & 0xFFFFFFFF))[0]
            except Exception:
                result[name.lower()] = None
        try:
            result["fpscr"] = self._jlink.register_read("FPSCR")
        except Exception:
            result["fpscr"] = None
        return result

    # -- Flash Operations --

    def erase_flash(
        self,
        start_address: int | None = None,
        end_address: int | None = None,
        chip_erase: bool = False,
    ) -> dict[str, Any]:
        self._require_connected()
        try:
            if chip_erase:
                self._jlink.erase()
                return {
                    "status": "ok",
                    "summary": "Chip erase completed.",
                    "chip_erase": True,
                    "start_address": None,
                    "end_address": None,
                }

            if start_address is None or end_address is None:
                raise ValueError(
                    "start_address and end_address are required when chip_erase is False."
                )
            if end_address <= start_address:
                raise ValueError("end_address must be greater than start_address.")

            size = end_address - start_address
            # pylink erase() only supports chip erase; for range erase,
            # write 0xFF via flash_write which erases sectors automatically
            self._jlink.flash_write(start_address, [0xFF] * size)
            return {
                "status": "ok",
                "summary": f"Erased flash range {hex(start_address)}-{hex(end_address)}.",
                "chip_erase": False,
                "start_address": hex(start_address),
                "end_address": hex(end_address),
            }
        except Exception as e:
            return {"status": "error", "summary": str(e)}

    def program_flash(
        self,
        address: int,
        data: bytes,
        verify: bool = True,
    ) -> dict[str, Any]:
        self._require_connected()
        try:
            if not data:
                raise ValueError("data must not be empty.")

            self._jlink.flash_write(address, list(data))
            result = {
                "status": "ok",
                "summary": f"Programmed {len(data)} byte(s) to flash at {hex(address)}.",
                "address": hex(address),
                "size": len(data),
                "verify": verify,
            }
            if verify:
                verify_result = self.verify_flash(address, data)
                if verify_result["status"] != "ok" or not verify_result.get("match", False):
                    return verify_result
            return result
        except Exception as e:
            return {"status": "error", "summary": str(e)}

    def verify_flash(self, address: int, data: bytes) -> dict[str, Any]:
        self._require_connected()
        try:
            if not data:
                raise ValueError("data must not be empty.")

            actual = bytes(self._jlink.memory_read8(address, len(data)))
            mismatch_count = 0
            first_mismatch_address = None
            for i, (expected_byte, actual_byte) in enumerate(zip(data, actual)):
                if expected_byte != actual_byte:
                    mismatch_count += 1
                    if first_mismatch_address is None:
                        first_mismatch_address = address + i

            match = mismatch_count == 0
            return {
                "status": "ok" if match else "error",
                "summary": (
                    f"Verified {len(data)} byte(s) at {hex(address)}."
                    if match
                    else f"Flash verification failed at {hex(first_mismatch_address)}."
                ),
                "address": hex(address),
                "size": len(data),
                "match": match,
                "mismatch_count": mismatch_count,
                "first_mismatch_address": None
                if first_mismatch_address is None
                else hex(first_mismatch_address),
            }
        except Exception as e:
            return {"status": "error", "summary": str(e)}

    def read_rtt_log(self, channel: int = 0, max_bytes: int = 4096) -> dict[str, Any]:
        self._require_connected()
        try:
            if not self._rtt_started:
                self._jlink.rtt_start()
                self._rtt_started = True

            up_buffers = self._jlink.rtt_get_num_up_buffers()
            if up_buffers <= 0:
                return {
                    "status": "error",
                    "summary": "J-Link RTT is active but no up-buffers were reported by the target.",
                }
            if channel >= up_buffers:
                return {
                    "status": "error",
                    "summary": f"RTT up-buffer channel {channel} is out of range (max {up_buffers - 1}).",
                }

            status = None
            try:
                status = self._jlink.rtt_get_status()
            except Exception:
                status = None
            if status is not None and not isinstance(status, (str, int, float, bool)):
                status = str(status)

            raw = bytes(self._jlink.rtt_read(channel, max_bytes))
            return {
                "status": "ok",
                "summary": f"Read {len(raw)} byte(s) from J-Link RTT channel {channel}.",
                "backend": "jlink",
                "channel": channel,
                "up_buffer_count": up_buffers,
                "rtt_status": status,
                "bytes_available": len(raw),
                "text": raw.decode("utf-8", errors="replace"),
                "cb_address": None,
                "buffer_size": None,
                "wr_off": None,
                "rd_off": None,
            }
        except Exception as e:
            return {"status": "error", "summary": str(e)}

    def read_cycle_counter(self) -> dict[str, Any]:
        self._require_connected()
        try:
            demcr = self._jlink.memory_read32(self._DEMCR, 1)[0]
            dwt_ctrl = self._jlink.memory_read32(self._DWT_CTRL, 1)[0]

            if (demcr & self._DEMCR_TRCENA) == 0:
                demcr |= self._DEMCR_TRCENA
                self._jlink.memory_write32(self._DEMCR, [demcr])
            if (dwt_ctrl & self._DWT_CTRL_CYCCNTENA) == 0:
                dwt_ctrl |= self._DWT_CTRL_CYCCNTENA
                self._jlink.memory_write32(self._DWT_CTRL, [dwt_ctrl])

            cyccnt = self._jlink.memory_read32(self._DWT_CYCCNT, 1)[0]
            dwt_ctrl_after = self._jlink.memory_read32(self._DWT_CTRL, 1)[0]
            return {
                "status": "ok",
                "summary": "Read DWT cycle counter.",
                "backend": "jlink",
                "cyccnt": int(cyccnt),
                "cyccnt_hex": hex(int(cyccnt)),
                "dwt_enabled": bool(dwt_ctrl_after & self._DWT_CTRL_CYCCNTENA),
            }
        except Exception as e:
            return {"status": "error", "summary": str(e)}

    def read_swo_log(
        self,
        cpu_speed_hz: int,
        swo_speed_hz: int,
        max_bytes: int = 1024,
        port_mask: int = 0x01,
    ) -> dict[str, Any]:
        self._require_connected()
        try:
            if cpu_speed_hz <= 0:
                raise ValueError("cpu_speed_hz must be greater than 0.")
            if swo_speed_hz <= 0:
                raise ValueError("swo_speed_hz must be greater than 0.")
            if max_bytes <= 0:
                raise ValueError("max_bytes must be greater than 0.")

            self._ensure_swo_config(
                cpu_speed_hz=cpu_speed_hz,
                swo_speed_hz=swo_speed_hz,
                port_mask=port_mask,
            )

            available = int(self._jlink.swo_num_bytes())
            to_read = min(max_bytes, max(available, 0))
            raw = bytes(self._jlink.swo_read_stimulus(0, to_read)) if to_read > 0 else b""
            return {
                "status": "ok",
                "summary": f"Read {len(raw)} byte(s) from SWO.",
                "backend": "jlink",
                "cpu_speed_hz": cpu_speed_hz,
                "swo_speed_hz": swo_speed_hz,
                "port_mask": port_mask,
                "bytes_available": available,
                "bytes_read": len(raw),
                "text": raw.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            return {"status": "error", "summary": str(e)}

    def read_itm_trace(
        self,
        cpu_speed_hz: int,
        swo_speed_hz: int,
        stimulus_port: int = 0,
        max_bytes: int = 1024,
        port_mask: int | None = None,
    ) -> dict[str, Any]:
        self._require_connected()
        try:
            if cpu_speed_hz <= 0:
                raise ValueError("cpu_speed_hz must be greater than 0.")
            if swo_speed_hz <= 0:
                raise ValueError("swo_speed_hz must be greater than 0.")
            if stimulus_port < 0:
                raise ValueError("stimulus_port must be greater than or equal to 0.")
            if max_bytes <= 0:
                raise ValueError("max_bytes must be greater than 0.")

            effective_port_mask = port_mask if port_mask is not None else (1 << stimulus_port)
            self._ensure_swo_config(
                cpu_speed_hz=cpu_speed_hz,
                swo_speed_hz=swo_speed_hz,
                port_mask=effective_port_mask,
            )

            available = int(self._jlink.swo_num_bytes())
            to_read = min(max_bytes, max(available, 0))
            raw = (
                bytes(self._jlink.swo_read_stimulus(stimulus_port, to_read)) if to_read > 0 else b""
            )
            return {
                "status": "ok",
                "summary": (f"Read {len(raw)} byte(s) from ITM stimulus port {stimulus_port}."),
                "backend": "jlink",
                "cpu_speed_hz": cpu_speed_hz,
                "swo_speed_hz": swo_speed_hz,
                "stimulus_port": stimulus_port,
                "port_mask": effective_port_mask,
                "bytes_available": available,
                "bytes_read": len(raw),
                "text": raw.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            return {"status": "error", "summary": str(e)}

    # -- Helpers --

    def _ensure_swo_config(self, cpu_speed_hz: int, swo_speed_hz: int, port_mask: int) -> None:
        requested_config = (cpu_speed_hz, swo_speed_hz, port_mask)
        if (not self._jlink.swo_enabled()) or (self._swo_config != requested_config):
            self._jlink.swo_enable(cpu_speed_hz, swo_speed_hz, port_mask=port_mask)
            self._swo_config = requested_config

    @classmethod
    def _default_dll_candidates(cls) -> list[str]:
        env_candidates = [
            value
            for value in (
                str(Path.home() / "AppData/Local/Programs/SEGGER/JLink/JLink_x64.dll"),
                str(Path.home() / "AppData/Local/Programs/SEGGER/JLink/JLinkARM.dll"),
            )
            if value
        ]
        return [
            *[
                value
                for value in (
                    os.environ.get("JLINK_X64_DLL"),
                    os.environ.get("JLINK_DLL"),
                    r"E:\software\jlink\JLink_x64.dll",
                    r"E:\software\jlink\JLinkARM.dll",
                    r"E:\software\MDK\ARM\Segger\JLink_x64.dll",
                    r"E:\software\MDK\ARM\Segger\JLinkARM.dll",
                    r"C:\Program Files\SEGGER\JLink\JLink_x64.dll",
                    r"C:\Program Files\SEGGER\JLink\JLinkARM.dll",
                    r"C:\Program Files (x86)\SEGGER\JLink\JLink_x64.dll",
                    r"C:\Program Files (x86)\SEGGER\JLink\JLinkARM.dll",
                    *env_candidates,
                )
                if value
            ]
        ]

    @classmethod
    def _resolve_dll_path(cls, dll_path: str | None = None) -> str:
        candidates = [dll_path] if dll_path else []
        candidates.extend(cls._default_dll_candidates())
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return str(Path(candidate))
        raise BackendUnavailableError(
            "J-Link DLL not found. Set probe.jlink_dll_path or install SEGGER J-Link."
        )

    @classmethod
    def _create_library(cls, dll_path: str | None = None):
        if pylink is None or pylink_library is None:
            raise BackendUnavailableError("pylink-square is not installed.")
        resolved = cls._resolve_dll_path(dll_path)
        try:
            return pylink_library.Library(resolved)
        except Exception as exc:
            raise BackendUnavailableError(f"Failed to load J-Link DLL '{resolved}': {exc}") from exc

    def _get_library(self):
        if self._library is None:
            self._library = self._create_library(self._dll_path)
            self._dll_path = (
                getattr(self._library, "_path", None) or self._dll_path or self._resolve_dll_path()
            )
        return self._library

    def _read_register(self, name: str) -> int:
        register_name = self._REGISTER_ALIASES.get(name.lower(), name)
        return self._jlink.register_read(register_name)

    def _run_target(self) -> None:
        if hasattr(self._jlink, "go"):
            self._jlink.go()
        else:
            self._jlink.restart()

    def _infer_stop_reason(self, pc: int) -> str:
        if self._matches_breakpoint(pc):
            return "breakpoint_hit"
        return "manual_halt"

    def _matches_breakpoint(self, pc: int) -> bool:
        if pc in self._breakpoints:
            return True
        if (pc - 2) in self._breakpoints:
            return True
        if (pc - 4) in self._breakpoints:
            return True
        return False

    def _require_library(self) -> None:
        if pylink is None or pylink_library is None:
            raise BackendUnavailableError("pylink-square is not installed.")
        self._get_library()

    def _require_connected(self) -> None:
        if not self._connected or self._jlink is None:
            raise BackendUnavailableError("J-Link probe is not connected.")
