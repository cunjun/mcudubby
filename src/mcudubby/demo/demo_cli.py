from __future__ import annotations

import json

from ..tools.diagnose import diagnose_hardfault, diagnose_startup_failure
from ..tools.probe import (
    clear_breakpoint,
    continue_target,
    list_conditional_breakpoints,
    set_breakpoint,
)
from .mock_backends import MockProbeBackend
from .mock_session import MockSessionState


class _R0CounterProbe(MockProbeBackend):
    """MockProbeBackend variant: r0 increments by 1 on each read_core_registers call.

    Simulates a retry counter so the conditional breakpoint demo can show
    real skip-hit behaviour (condition: r0 >= 3, hits on 4th call).
    """

    def __init__(self) -> None:
        super().__init__()
        self._r0 = 0

    def read_core_registers(self) -> dict:
        self._require_connected()
        regs = super().read_core_registers()
        regs["r0"] = self._r0
        self._r0 += 1
        return regs

    def continue_target(self, timeout_seconds=5.0, poll_interval_seconds=0.05):
        self._require_connected()
        self._halted = True
        return {
            "status": "ok",
            "summary": "Mock target stopped after continue.",
            "stop_reason": "breakpoint_hit",
            "state": self.get_state(),
            "pc": hex(0x08004567),  # always returns sensor_init address
        }


def run_demo() -> None:
    session = MockSessionState()

    print("== McuBubby mock demo ==")
    print()
    print("User: This STM32L4 board doesn't boot after power-on. Help me inspect it.")
    print()

    print("[1/4] Connect UART log")
    print(json.dumps(session.log.connect(port="COM-MOCK", baudrate=115200), indent=2))
    print()

    print("[2/4] Connect probe (pyOCD / ST-Link path)")
    print(json.dumps(session.probe.connect(target="stm32l4"), indent=2))
    print()

    print("[3/4] Load ELF")
    print(json.dumps(session.elf.load("firmware.elf"), indent=2))
    print()

    print("[4/4] Diagnose startup failure")
    startup = diagnose_startup_failure(session, suspected_stage="sensor init")
    print(json.dumps(startup, indent=2))
    print()

    print("HardFault-focused result")
    hardfault = diagnose_hardfault(session, suspected_stage="sensor init")
    print(json.dumps(hardfault, indent=2))


def run_conditional_breakpoint_demo() -> None:
    """
    Demo: conditional breakpoint workflow.

    Scenario: the AI wants to halt at sensor_init only when r0 >= 3
    (i.e., the third or later retry attempt). All earlier hits are
    transparently skipped by continue_target.

    Usage (AI perspective):
        1. set_breakpoint(symbol="sensor_init", condition_register="r0",
                          condition_op="ge", condition_value=3)
        2. continue_target()   - automatically skips r0<3 hits
        3. Inspect registers / locals when halted
        4. clear_breakpoint(symbol="sensor_init")
    """
    # Use the r0-counter probe so we can demonstrate real skip-hit behaviour.
    session = MockSessionState()
    session.probe = _R0CounterProbe()
    session.probe.connect(target="stm32l4")
    session.elf.load("firmware.elf")

    print("== Conditional breakpoint demo ==")
    print("Scenario: halt at sensor_init only when r0 >= 3 (3rd+ retry).")
    print("r0 increments by 1 on each breakpoint hit.")
    print()

    bp_addr = 0x08004567  # resolves to sensor_init in MockElfManager
    print("[1/4] Set conditional breakpoint at sensor_init when r0 >= 3")
    result = set_breakpoint(
        session,
        address=bp_addr,
        condition_register="r0",
        condition_op="ge",
        condition_value=3,
        confirm=True,
    )
    print(json.dumps(result, indent=2))
    print()

    print("[2/4] List registered conditional breakpoints")
    print(json.dumps(list_conditional_breakpoints(session), indent=2))
    print()

    print("[3/4] continue_target - skips r0=0,1,2; halts on r0=3")
    result = continue_target(session, max_condition_loops=20)
    print(json.dumps(result, indent=2))
    print()

    print("[4/4] Clear conditional breakpoint")
    print(json.dumps(clear_breakpoint(session, address=bp_addr, confirm=True), indent=2))
    print("conditional_breakpoints after clear:", session.conditional_breakpoints)


if __name__ == "__main__":
    run_demo()
    print()
    run_conditional_breakpoint_demo()
