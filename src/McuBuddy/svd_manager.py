"""SVD peripheral register manager.

Loads a CMSIS-SVD file and provides field-level interpretation of peripheral
register values read from the connected probe.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from cmsis_svd.parser import SVDParser

    _SVD_AVAILABLE = True
except ImportError:
    SVDParser = None  # type: ignore[assignment,misc]
    _SVD_AVAILABLE = False

if TYPE_CHECKING:
    pass


_KNOWN_PERIPHERAL_DESCRIPTIONS: dict[str, str] = {
    "USART": "Universal Synchronous/Asynchronous Receiver/Transmitter",
    "UART": "Universal Asynchronous Receiver/Transmitter",
    "SPI": "Serial Peripheral Interface",
    "I2C": "Inter-Integrated Circuit",
    "GPIO": "General Purpose Input/Output",
    "TIM": "Timer",
    "ADC": "Analog-to-Digital Converter",
    "DAC": "Digital-to-Analog Converter",
    "DMA": "Direct Memory Access",
    "RCC": "Reset and Clock Control",
    "EXTI": "External Interrupt/Event Controller",
    "NVIC": "Nested Vectored Interrupt Controller",
    "FLASH": "Flash Memory Controller",
    "PWR": "Power Control",
    "IWDG": "Independent Watchdog",
    "WWDG": "Window Watchdog",
    "RTC": "Real-Time Clock",
    "CRC": "CRC Calculation Unit",
    "USB": "Universal Serial Bus",
    "CAN": "Controller Area Network",
}


class SvdManager:
    """Manages SVD file loading and peripheral register interpretation."""

    def __init__(self) -> None:
        self._path: Path | None = None
        self._device: Any | None = None
        self._peripheral_map: dict[str, Any] = {}

    @property
    def is_loaded(self) -> bool:
        return self._device is not None

    @property
    def path(self) -> Path | None:
        return self._path

    def load(self, path: str) -> dict[str, Any]:
        """Load an SVD file from disk."""
        if not _SVD_AVAILABLE:
            return {
                "status": "error",
                "summary": "cmsis-svd package is not installed. Run: pip install cmsis-svd",
            }

        file_path = Path(path)
        if not file_path.exists():
            return {
                "status": "error",
                "summary": f"SVD file not found: {path}",
            }

        parser = SVDParser.for_xml_file(file_path)
        self._device = parser.get_device()
        self._path = file_path

        self._peripheral_map = {}
        for periph in self._device.peripherals:
            self._peripheral_map[periph.name.upper()] = periph

        return {
            "status": "ok",
            "summary": f"Loaded SVD: {file_path.name} ({self._device.name})",
            "device": self._device.name,
            "peripheral_count": len(self._peripheral_map),
        }

    def list_peripherals(self) -> dict[str, Any]:
        """List all peripherals defined in the loaded SVD."""
        if not self.is_loaded:
            return {
                "status": "error",
                "summary": "No SVD file loaded. Call svd_load first.",
            }

        peripherals = []
        for name, periph in sorted(self._peripheral_map.items()):
            category = next(
                (
                    desc
                    for key, desc in _KNOWN_PERIPHERAL_DESCRIPTIONS.items()
                    if name.startswith(key)
                ),
                "Peripheral",
            )
            peripherals.append(
                {
                    "name": name,
                    "base_address": hex(periph.base_address),
                    "description": periph.description or category,
                    "category": category,
                }
            )

        return {
            "status": "ok",
            "summary": f"Found {len(peripherals)} peripherals.",
            "peripherals": peripherals,
        }

    def get_peripheral_registers(self, peripheral_name: str) -> dict[str, Any]:
        """Return register layout for a peripheral (no hardware read)."""
        periph = self._resolve_peripheral(peripheral_name)
        if periph is None:
            return self._peripheral_not_found(peripheral_name)

        registers = self._collect_registers(periph)
        return {
            "status": "ok",
            "summary": f"Found {len(registers)} registers in {periph.name}.",
            "peripheral": periph.name,
            "base_address": hex(periph.base_address),
            "registers": [
                {
                    "name": r["name"],
                    "address": hex(periph.base_address + r["offset"]),
                    "offset": hex(r["offset"]),
                    "description": r["description"],
                    "fields": [
                        {
                            "name": f["name"],
                            "bits": f["bits"],
                            "description": f["description"],
                        }
                        for f in r["fields"]
                    ],
                }
                for r in registers
            ],
        }

    def read_peripheral_state(
        self,
        peripheral_name: str,
        probe: Any,
    ) -> dict[str, Any]:
        """Read all register values for a peripheral and interpret each field."""
        periph = self._resolve_peripheral(peripheral_name)
        if periph is None:
            return self._peripheral_not_found(peripheral_name)

        registers = self._collect_registers(periph)
        interpreted = []
        errors = []

        for reg in registers:
            addr = periph.base_address + reg["offset"]
            try:
                raw_bytes = probe.read_memory(addr, 4)
                value = int.from_bytes(raw_bytes, "little")
                decoded = self._decode_register(value, reg["fields"])
                interpreted.append(
                    {
                        "name": reg["name"],
                        "address": hex(addr),
                        "value": hex(value),
                        "description": reg["description"],
                        "fields": decoded,
                        "interpretation": self._summarize_register(reg["name"], decoded),
                    }
                )
            except Exception as exc:
                errors.append({"register": reg["name"], "error": str(exc)})

        diagnosis = self._diagnose_peripheral(periph.name, interpreted, periph.base_address)

        return {
            "status": "ok",
            "summary": f"Read {len(interpreted)} register(s) from {periph.name}.",
            "peripheral": periph.name,
            "base_address": hex(periph.base_address),
            "registers": interpreted,
            "errors": errors,
            "diagnosis": diagnosis,
        }

    def write_register(
        self,
        peripheral_name: str,
        register_name: str,
        value: int,
        probe: Any,
    ) -> dict[str, Any]:
        if not self.is_loaded:
            return {"status": "error", "summary": "No SVD file loaded. Call svd_load first."}
        periph = self._resolve_peripheral(peripheral_name)
        if periph is None:
            return self._peripheral_not_found(peripheral_name)
        registers = self._collect_registers(periph)
        reg = next((r for r in registers if r["name"].upper() == register_name.upper()), None)
        if reg is None:
            available = [r["name"] for r in registers]
            return {
                "status": "error",
                "summary": f"Register '{register_name}' not found in {periph.name}.",
                "available_registers": available,
            }
        addr = periph.base_address + reg["offset"]
        try:
            raw = value.to_bytes(4, "little")
            probe.write_memory(addr, raw)
        except Exception as e:
            return {"status": "error", "summary": str(e)}
        return {
            "status": "ok",
            "summary": f"Wrote {hex(value)} to {periph.name}.{reg['name']} at {hex(addr)}.",
            "peripheral": periph.name,
            "register": reg["name"],
            "address": hex(addr),
            "value": hex(value),
        }

    def write_field(
        self,
        peripheral_name: str,
        register_name: str,
        field_name: str,
        value: int,
        probe: Any,
    ) -> dict[str, Any]:
        try:
            periph = self._resolve_peripheral(peripheral_name)
            if periph is None:
                return self._peripheral_not_found(peripheral_name)

            registers = self._collect_registers(periph)
            reg = next((r for r in registers if r["name"].upper() == register_name.upper()), None)
            if reg is None:
                available = [r["name"] for r in registers]
                return {
                    "status": "error",
                    "summary": f"Register '{register_name}' not found in {periph.name}.",
                    "available_registers": available,
                }

            field = next(
                (f for f in reg["fields"] if f["name"].upper() == field_name.upper()), None
            )
            if field is None:
                return {
                    "status": "error",
                    "summary": f"Field '{field_name}' not found in {periph.name}.{reg['name']}.",
                    "available_fields": [f["name"] for f in reg["fields"]],
                }

            field_width = int(field["bit_width"])
            if value < 0 or value >= (1 << field_width):
                return {
                    "status": "error",
                    "summary": (
                        f"Value {value} does not fit in field {periph.name}.{reg['name']}.{field['name']} "
                        f"(width={field_width})."
                    ),
                }

            addr = periph.base_address + reg["offset"]
            raw = probe.read_memory(addr, 4)
            current = int.from_bytes(raw, "little")

            mask = ((1 << field_width) - 1) << field["bit_offset"]
            new_val = (current & ~mask) | (
                (value & ((1 << field_width) - 1)) << field["bit_offset"]
            )

            probe.write_memory(addr, new_val.to_bytes(4, "little"))

            return {
                "status": "ok",
                "summary": (
                    f"Set {periph.name}.{reg['name']}.{field['name']} = {value} "
                    f"(wrote {hex(new_val)} to {hex(addr)})."
                ),
                "peripheral": periph.name,
                "register": reg["name"],
                "field": field["name"],
                "address": hex(addr),
                "old_register_value": hex(current),
                "new_register_value": hex(new_val),
                "field_value": value,
            }
        except Exception as e:
            return {"status": "error", "summary": str(e)}

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _resolve_peripheral(self, name: str) -> Any | None:
        key = name.upper()
        return self._peripheral_map.get(key)

    def _peripheral_not_found(self, name: str) -> dict[str, Any]:
        available = sorted(self._peripheral_map.keys())
        close = [n for n in available if name.upper() in n or n in name.upper()]
        return {
            "status": "error",
            "summary": f"Peripheral '{name}' not found in SVD.",
            "suggestions": close or available[:10],
        }

    def _collect_registers(self, periph: Any) -> list[dict[str, Any]]:
        """Collect all registers from a peripheral (handles derived peripherals)."""
        registers = periph.registers or []
        result = []
        for reg in registers:
            fields = []
            for field in reg.fields or []:
                msb = field.bit_offset + field.bit_width - 1
                bits = (
                    str(field.bit_offset) if field.bit_width == 1 else f"{msb}:{field.bit_offset}"
                )
                fields.append(
                    {
                        "name": field.name,
                        "bits": bits,
                        "bit_offset": field.bit_offset,
                        "bit_width": field.bit_width,
                        "description": (field.description or "").replace("\n", " ").strip(),
                    }
                )
            result.append(
                {
                    "name": reg.name,
                    "offset": reg.address_offset,
                    "description": (reg.description or "").replace("\n", " ").strip(),
                    "fields": sorted(fields, key=lambda f: f["bit_offset"], reverse=True),
                }
            )
        return sorted(result, key=lambda r: r["offset"])

    def _decode_register(self, value: int, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        decoded = []
        for field in fields:
            offset = field["bit_offset"]
            width = field["bit_width"]
            mask = (1 << width) - 1
            field_value = (value >> offset) & mask
            decoded.append(
                {
                    "name": field["name"],
                    "bits": field["bits"],
                    "value": field_value,
                    "hex": hex(field_value),
                    "description": field["description"],
                }
            )
        return decoded

    def _summarize_register(self, reg_name: str, fields: list[dict[str, Any]]) -> str:
        """Produce a short human-readable summary of active fields."""
        active = [f for f in fields if f["value"] != 0]
        if not active:
            return f"{reg_name}: all fields zero"
        parts = [f"{f['name']}={f['value']}" for f in active[:6]]
        suffix = f" (+{len(active) - 6} more)" if len(active) > 6 else ""
        return f"{reg_name}: {', '.join(parts)}{suffix}"

    def _diagnose_peripheral(
        self, periph_name: str, registers: list[dict[str, Any]], base_address: int = 0
    ) -> list[str]:
        """Generate diagnosis notes based on common peripheral misconfiguration patterns."""
        notes: list[str] = []
        # Build reg_map by name; also add offset-based aliases so diagnosis
        # works even when SVD register names are malformed (e.g. "0x00000000").
        reg_map = {r["name"]: r for r in registers}
        offset_map = {hex(int(r["address"], 16) - base_address): r for r in registers}
        _ALIASES = {
            "CR1": "0x0",
            "CR2": "0x4",
            "CR3": "0x8",
            "BRR": "0xc",
            "ISR": "0x1c",
            "SR": "0x8",
            "MODER": "0x0",
            "IDR": "0x10",
            "ODR": "0x14",
        }
        for canonical, offset_hex in _ALIASES.items():
            if canonical not in reg_map and offset_hex in offset_map:
                reg_map[canonical] = offset_map[offset_hex]
        name_upper = periph_name.upper()
        if name_upper.startswith(("USART", "UART")):
            notes.extend(_diagnose_uart(reg_map))
        elif name_upper.startswith("SPI"):
            notes.extend(_diagnose_spi(reg_map))
        elif name_upper.startswith("I2C"):
            notes.extend(_diagnose_i2c(reg_map))
        elif name_upper.startswith("GPIO"):
            notes.extend(_diagnose_gpio(reg_map))
        elif name_upper.startswith("RCC"):
            notes.append("RCC registers read. Check enable bits for target peripherals.")

        if not notes:
            notes.append("No common misconfiguration patterns detected.")

        return notes


# ------------------------------------------------------------------ #
# Peripheral-specific diagnosis helpers
# ------------------------------------------------------------------ #


def _field_value(registers: dict, reg_name: str, field_name: str) -> int | None:
    reg = registers.get(reg_name)
    if reg is None:
        return None
    for f in reg.get("fields", []):
        if f["name"] == field_name:
            return f["value"]
    return None


def _diagnose_uart(regs: dict) -> list[str]:
    notes = []
    ue = _field_value(regs, "CR1", "UE")
    te = _field_value(regs, "CR1", "TE")
    re = _field_value(regs, "CR1", "RE")

    if ue == 0:
        notes.append("USART is disabled (CR1.UE=0). Enable with CR1.UE=1.")
    if te == 0:
        notes.append("Transmitter is disabled (CR1.TE=0). No TX output possible.")
    if re == 0:
        notes.append("Receiver is disabled (CR1.RE=0). No RX reception possible.")
    if ue == 1 and te == 1:
        notes.append("Transmitter is enabled and USART is active.")
    return notes


def _diagnose_spi(regs: dict) -> list[str]:
    notes = []
    spe = _field_value(regs, "CR1", "SPE")
    mstr = _field_value(regs, "CR1", "MSTR")

    if spe == 0:
        notes.append("SPI is disabled (CR1.SPE=0). Enable to start transfers.")
    if mstr == 1:
        notes.append("SPI is in master mode (CR1.MSTR=1).")
    elif mstr == 0:
        notes.append("SPI is in slave mode (CR1.MSTR=0).")
    return notes


def _diagnose_i2c(regs: dict) -> list[str]:
    notes = []
    pe = _field_value(regs, "CR1", "PE")
    busy = _field_value(regs, "ISR", "BUSY")
    nackf = _field_value(regs, "ISR", "NACKF")

    if pe == 0:
        notes.append("I2C is disabled (CR1.PE=0). Enable to start communication.")
    if busy == 1:
        notes.append("I2C bus is busy (ISR.BUSY=1). May indicate a stuck bus.")
    if nackf == 1:
        notes.append("NACK received (ISR.NACKF=1). Target device not responding.")
    return notes


def _diagnose_gpio(regs: dict) -> list[str]:
    notes = []
    moder = regs.get("MODER")
    odr = regs.get("ODR")
    idr = regs.get("IDR")

    if moder:
        notes.append("GPIO MODER read. Check pin mode (00=input, 01=output, 10=AF, 11=analog).")
    if odr and idr:
        odr_val = int(odr["value"], 16)
        idr_val = int(idr["value"], 16)
        if odr_val != idr_val:
            diff = odr_val ^ idr_val
            pins = [i for i in range(16) if (diff >> i) & 1]
            notes.append(
                f"ODR and IDR differ on pin(s) {pins}. "
                "Output pins may be driving against an external signal."
            )
    return notes
