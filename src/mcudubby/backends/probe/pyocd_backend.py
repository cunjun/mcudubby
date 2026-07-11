from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ...errors import BackendUnavailableError
from .base import ProbeBackend

try:
    from pyocd.core.helpers import ConnectHelper
    from pyocd.core.target import Target
except ImportError:  # pragma: no cover
    ConnectHelper = None
    Target = None


_DEFAULT_PACK_PATTERNS = {
    "py32f030x8": ["Puya.PY32F0xx_DFP.*.pack"],
}


def _discover_default_pack_paths(target: str) -> list[str]:
    normalized_target = "".join(ch for ch in target.strip().lower() if ch.isalnum())
    patterns = _DEFAULT_PACK_PATTERNS.get(normalized_target)
    if not patterns:
        return []

    search_roots = [
        Path.cwd() / "packs",
        Path(__file__).resolve().parents[4] / "packs",
    ]
    discovered: list[str] = []
    seen: set[Path] = set()
    for root in search_roots:
        if not root.is_dir():
            continue
        for pattern in patterns:
            for pack_path in sorted(root.glob(pattern)):
                resolved = pack_path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                discovered.append(str(resolved))
    return discovered


class PyOcdProbeBackend(ProbeBackend):
    """Minimal pyOCD probe backend for v0.1."""

    @classmethod
    def enumerate_probes(cls) -> list[dict]:
        if ConnectHelper is None:
            return []
        try:
            probes = ConnectHelper.get_all_connected_probes(blocking=False)
            return [
                {
                    "unique_id": probe.unique_id,
                    "description": probe.description,
                    "vendor_name": getattr(probe, "vendor_name", None),
                    "product_name": getattr(probe, "product_name", None),
                }
                for probe in probes
            ]
        except Exception:
            return []

    def __init__(self) -> None:
        self._session = None
        self._target = None
        self._probe_name = "pyocd"
        self._breakpoints: set[int] = set()
        self._watchpoints: dict[int, tuple[int, Any, str]] = {}
        self._connect_hints: dict[str, Any] = {}
        self._pack_paths: list[str] = []

    def set_connect_hints(self, hints: dict[str, Any]) -> None:
        self._connect_hints = dict(hints)

    def set_pack_paths(self, pack_paths: list[str] | None) -> None:
        self._pack_paths = list(pack_paths or [])

    def connect(self, target: str, unique_id: str | None = None) -> dict[str, Any]:
        if ConnectHelper is None:
            raise BackendUnavailableError("pyocd is not installed")

        if self._session is not None:
            self.disconnect()

        attempted_configs: list[dict[str, Any]] = []
        last_error: Exception | None = None
        attempts = self._connect_hints.get(
            "attempts",
            [
                {"frequency": 4000000, "connect_mode": "attach"},
                {"frequency": 1000000, "connect_mode": "attach"},
                {"frequency": 1000000, "connect_mode": "under-reset"},
            ],
        )
        pack_paths = self._pack_paths or _discover_default_pack_paths(target)

        for attempt in attempts:
            attempted_configs.append(dict(attempt))
            try:
                session = ConnectHelper.session_with_chosen_probe(
                    unique_id=unique_id,
                    target_override=target,
                    frequency=attempt["frequency"],
                    blocking=False,
                    connect_mode=attempt["connect_mode"],
                    pack=pack_paths or None,
                )
                if session is None:
                    continue
                session.open()
                self._session = session
                self._target = session.target
                return {
                    "status": "ok",
                    "summary": f"Connected to target {target} via pyOCD probe backend.",
                    "backend": self._probe_name,
                    "target": target,
                    "frequency_hz": attempt["frequency"],
                    "connect_mode": attempt["connect_mode"],
                    "attempted_configs": attempted_configs,
                    "pack_paths": list(pack_paths),
                }
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            raise BackendUnavailableError(
                f"no supported pyOCD probe could be opened for target {target}; attempts={attempted_configs}; last_error={last_error}"
            )
        raise BackendUnavailableError(
            f"no supported pyOCD probe could be opened for target {target}; attempts={attempted_configs}"
        )

    def disconnect(self) -> dict[str, Any]:
        if self._session is not None:
            self._session.close()
        self._session = None
        self._target = None
        self._breakpoints.clear()
        self._watchpoints.clear()
        return {"status": "ok", "summary": "Disconnected probe session."}

    def halt(self) -> dict[str, Any]:
        self._require_target()
        self._target.halt()
        return {"status": "ok", "summary": "Target halted."}

    def resume(self) -> dict[str, Any]:
        self._require_target()
        self._target.resume()
        return {"status": "ok", "summary": "Target resumed."}

    def reset(self, halt: bool = False) -> dict[str, Any]:
        self._require_target()
        if halt:
            self._target.reset_and_halt()
            return {"status": "ok", "summary": "Target reset and halted."}
        self._target.reset()
        return {"status": "ok", "summary": "Target reset."}

    def set_breakpoint(self, address: int) -> dict[str, Any]:
        self._require_target()
        normalized_address = int(address) & ~1
        success = bool(self._target.set_breakpoint(normalized_address))
        if not success:
            raise BackendUnavailableError(f"failed to set breakpoint at {hex(normalized_address)}")
        self._breakpoints.add(normalized_address)
        return {
            "status": "ok",
            "summary": f"Breakpoint set at {hex(normalized_address)}.",
            "address": hex(normalized_address),
        }

    def clear_breakpoint(self, address: int) -> dict[str, Any]:
        self._require_target()
        normalized_address = int(address) & ~1
        self._target.remove_breakpoint(normalized_address)
        self._breakpoints.discard(normalized_address)
        return {
            "status": "ok",
            "summary": f"Breakpoint cleared at {hex(normalized_address)}.",
            "address": hex(normalized_address),
        }

    def clear_all_breakpoints(self) -> dict[str, Any]:
        self._require_target()
        for address in list(self._breakpoints):
            self._target.remove_breakpoint(address)
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
        self._require_target()
        self._target.resume()

        deadline = time.monotonic() + timeout_seconds
        last_state = self._target.get_state()
        while time.monotonic() < deadline:
            state = self._target.get_state()
            last_state = state
            if Target is not None and state != Target.State.RUNNING:
                break
            time.sleep(poll_interval_seconds)
        else:
            self._target.halt()
            core = self.read_core_registers()
            return {
                "status": "ok",
                "summary": "Target did not stop before timeout and was halted for analysis.",
                "stop_reason": "timeout",
                "state": self.get_state(),
                "pc": hex(core["pc"]),
            }

        core = self.read_core_registers()
        stop_reason = self._infer_stop_reason(core["pc"], last_state)
        return {
            "status": "ok",
            "summary": "Target stopped after continue.",
            "stop_reason": stop_reason,
            "state": self.get_state(),
            "pc": hex(core["pc"]),
        }

    def get_state(self) -> str:
        self._require_target()
        state = self._target.get_state()
        return getattr(state, "name", str(state)).lower()

    def read_core_registers(self) -> dict[str, int]:
        self._require_target()
        names = [
            "r0",
            "r1",
            "r2",
            "r3",
            "r4",
            "r5",
            "r6",
            "r7",
            "r8",
            "r9",
            "r10",
            "r11",
            "r12",
            "sp",
            "lr",
            "pc",
            "xpsr",
        ]
        return {name: int(self._target.read_core_register(name)) for name in names}

    def read_fault_registers(self) -> dict[str, int]:
        self._require_target()
        fault_map = {
            "cfsr": 0xE000ED28,
            "hfsr": 0xE000ED2C,
            "mmfar": 0xE000ED34,
            "bfar": 0xE000ED38,
            "shcsr": 0xE000ED24,
        }
        return {name: int(self._target.read32(address)) for name, address in fault_map.items()}

    def read_memory(self, address: int, size: int) -> bytes:
        self._require_target()
        data = self._target.read_memory_block8(address, size)
        return bytes(data)

    def write_memory(self, address: int, data: bytes) -> None:
        self._require_target()
        self._target.write_memory_block8(address, list(data))

    def step(self) -> dict[str, Any]:
        self._require_target()
        self._target.step()
        core = self.read_core_registers()
        result: dict[str, Any] = {
            "status": "ok",
            "summary": "Executed one instruction.",
            "pc": hex(core["pc"]),
        }
        return result

    def _require_target(self) -> None:
        if self._target is None:
            raise BackendUnavailableError("probe target is not connected")

    def _infer_stop_reason(self, pc: int, state: Any) -> str:
        if Target is not None and state == Target.State.LOCKUP:
            return "fault"
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

    def set_watchpoint(self, address: int, size: int, watch_type: str) -> dict[str, Any]:
        self._require_target()
        if Target is None:
            raise BackendUnavailableError("pyocd is not installed")
        type_map = {
            "read": Target.WatchpointType.READ,
            "write": Target.WatchpointType.WRITE,
            "read_write": Target.WatchpointType.READ_WRITE,
        }
        wp_type = type_map.get(watch_type)
        if wp_type is None:
            raise ValueError(f"Invalid watch_type '{watch_type}'. Use: read, write, read_write")
        self._target.set_watchpoint(address, size, wp_type)
        self._watchpoints[int(address)] = (int(size), wp_type, watch_type)
        return {
            "status": "ok",
            "summary": f"Watchpoint set at {hex(address)}, size={size}, type={watch_type}.",
            "address": hex(address),
            "size": size,
            "watch_type": watch_type,
        }

    def remove_watchpoint(self, address: int) -> dict[str, Any]:
        self._require_target()
        watchpoint = self._watchpoints.get(int(address))
        if watchpoint is None:
            raise BackendUnavailableError(f"watchpoint at {hex(address)} is not set")
        size, wp_type, _watch_type = watchpoint
        self._target.remove_watchpoint(int(address), size, wp_type)
        self._watchpoints.pop(int(address), None)
        return {
            "status": "ok",
            "summary": f"Watchpoint removed at {hex(address)}.",
            "address": hex(address),
        }

    def clear_all_watchpoints(self) -> dict[str, Any]:
        self._require_target()
        for address, (size, wp_type, _watch_type) in list(self._watchpoints.items()):
            self._target.remove_watchpoint(address, size, wp_type)
        cleared = len(self._watchpoints)
        self._watchpoints.clear()
        return {
            "status": "ok",
            "summary": f"Cleared {cleared} watchpoint(s).",
            "cleared_count": cleared,
        }

    def read_fpu_registers(self) -> dict[str, Any]:
        self._require_target()
        result: dict[str, Any] = {}
        for index in range(32):
            name = f"s{index}"
            try:
                result[name] = self._target.read_core_register(name)
            except Exception:
                result[name] = None
        try:
            result["fpscr"] = self._target.read_core_register("fpscr")
        except Exception:
            result["fpscr"] = None
        return result

    def erase_flash(
        self,
        start_address: int | None = None,
        end_address: int | None = None,
        chip_erase: bool = False,
    ) -> dict[str, Any]:
        self._require_target()
        flash = self._get_flash()

        try:
            if chip_erase:
                flash.init(flash.Operation.ERASE, reset=True)
                try:
                    flash.erase_all()
                finally:
                    try:
                        flash.cleanup()
                    except Exception:
                        pass
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

            flash.init(flash.Operation.ERASE, address=start_address, reset=True)
            try:
                addr = start_address
                while addr < end_address:
                    flash.erase_sector(addr)
                    sector_info = flash.get_sector_info(addr)
                    sector_size = int(getattr(sector_info, "size", 0))
                    if sector_size <= 0:
                        raise BackendUnavailableError(f"invalid flash sector size at {hex(addr)}")
                    addr += sector_size
            finally:
                try:
                    flash.cleanup()
                except Exception:
                    pass

            return {
                "status": "ok",
                "summary": f"Erased flash range {hex(start_address)}-{hex(end_address)}.",
                "chip_erase": False,
                "start_address": hex(start_address),
                "end_address": hex(end_address),
            }
        except Exception as e:
            return {
                "status": "error",
                "summary": str(e),
            }

    def program_flash(
        self,
        address: int,
        data: bytes,
        verify: bool = True,
    ) -> dict[str, Any]:
        self._require_target()
        flash = self._get_flash()

        try:
            if not data:
                raise ValueError("data must not be empty.")

            flash.init(flash.Operation.PROGRAM, address=address, reset=True)
            try:
                offset = 0
                while offset < len(data):
                    page_info = flash.get_page_info(address + offset)
                    page_size = int(getattr(page_info, "size", 0))
                    if page_size <= 0:
                        raise BackendUnavailableError(
                            f"invalid flash page size at {hex(address + offset)}"
                        )
                    chunk = data[offset : offset + page_size]
                    flash.program_page(address + offset, chunk)
                    offset += len(chunk)
            finally:
                try:
                    flash.cleanup()
                except Exception:
                    pass

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
            return {
                "status": "error",
                "summary": str(e),
            }

    def verify_flash(self, address: int, data: bytes) -> dict[str, Any]:
        self._require_target()
        try:
            if not data:
                raise ValueError("data must not be empty.")

            actual = self.read_memory(address, len(data))
            mismatch_count = 0
            first_mismatch_address = None
            for index, (expected_byte, actual_byte) in enumerate(zip(data, actual)):
                if expected_byte != actual_byte:
                    mismatch_count += 1
                    if first_mismatch_address is None:
                        first_mismatch_address = address + index

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
            return {
                "status": "error",
                "summary": str(e),
            }

    def _get_flash(self) -> Any:
        flash = getattr(self._target, "flash", None)
        if flash is not None:
            return flash

        memory_map = getattr(self._target, "memory_map", None)
        if memory_map is not None:
            for region in memory_map:
                if (
                    getattr(region, "is_flash", False)
                    and getattr(region, "flash", None) is not None
                ):
                    return region.flash

        raise BackendUnavailableError("flash programming is not available for this target")
