from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


def _breakpoint_addresses(probe: object) -> frozenset[int]:
    addresses = getattr(probe, "breakpoint_addresses", None)
    if addresses is None:
        addresses = getattr(probe, "_breakpoints", ())
    return frozenset(int(address) & ~1 for address in addresses)


@contextmanager
def temporary_breakpoint(probe: object, address: int) -> Iterator[bool]:
    """Install a breakpoint for one workflow and remove it only when we created it."""
    normalized = int(address) & ~1
    created = normalized not in _breakpoint_addresses(probe)
    if created:
        probe.set_breakpoint(normalized)
    try:
        yield created
    finally:
        if created:
            probe.clear_breakpoint(normalized)
