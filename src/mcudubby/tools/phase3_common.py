from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..session import SessionState


def _probe_is_connected(session: SessionState) -> bool:
    """Return True if the probe appears to be connected.

    Reads the Cortex-M SCS ICTR register (0xE000E000), which is always
    accessible on any Cortex-M core regardless of MPU configuration or
    boot-mode memory remapping.  Using 0x0 (vector table) is unreliable
    because MPU policies or BOOT pin remapping can make that region
    inaccessible even with a fully functional probe.
    """
    try:
        session.probe.read_memory(0xE000E000, 4)
        return True
    except Exception:
        return False
