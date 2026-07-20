from __future__ import annotations

from ...session import SessionState


def log_trace(
    session: SessionState,
    max_steps: int = 200,
    max_lines: int = 50,
) -> dict:
    """Step through code recording each unique source line visited.

    Executes up to max_steps instructions, collecting distinct (file, line) pairs.
    Stops early once max_lines unique source lines have been seen.
    Requires ELF with .debug_line loaded.
    """
    if not session.elf.is_loaded:
        return {"status": "error", "summary": "ELF not loaded."}

    trace: list[dict] = []  # ordered unique source lines
    seen: set[tuple] = set()
    steps = 0
    try:
        for _ in range(max_steps):
            core = session.probe.read_core_registers()
            pc = core["pc"] & ~1
            src = session.elf.addr_to_source(pc)
            if src["file"] and src["line"]:
                key = (src["file"], src["line"])
                if key not in seen:
                    seen.add(key)
                    trace.append(
                        {
                            "file": src["file"],
                            "line": src["line"],
                            "pc": hex(pc),
                            "symbol": session.elf.resolve_address(pc).get("symbol"),
                        }
                    )
                    if len(trace) >= max_lines:
                        break
            session.probe.step()
            steps += 1
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
            "steps_completed": steps,
            "trace": trace,
        }

    return {
        "status": "ok",
        "summary": f"Traced {steps} instructions → {len(trace)} unique source line(s).",
        "steps": steps,
        "unique_lines": len(trace),
        "trace": trace,
    }


def reset_and_trace(
    session: SessionState,
    max_steps: int = 200,
    max_lines: int = 50,
) -> dict:
    """Reset target, halt, then immediately trace execution from reset vector."""
    try:
        session.probe.reset(halt=True)
    except Exception as e:
        return {"status": "error", "summary": f"Reset failed: {e}"}
    result = log_trace(session, max_steps=max_steps, max_lines=max_lines)
    result["summary"] = "Reset+trace: " + result.get("summary", "")
    return result
