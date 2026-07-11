from __future__ import annotations

from ..session import SessionState


def disconnect_all(session: SessionState) -> dict:
    results: dict[str, dict] = {}
    errors: dict[str, str] = {}

    actions: dict[str, object] = {
        "probe": session.probe.disconnect,
        "log": session.log.disconnect,
    }
    gdb_server = getattr(session, "gdb_server", None)
    if gdb_server is not None and hasattr(gdb_server, "stop"):
        actions["gdb_server"] = gdb_server.stop

    for name, action in actions.items():
        try:
            results[name] = action()
        except Exception as exc:
            errors[name] = str(exc)

    return {
        "status": "ok" if not errors else "partial",
        "summary": (
            "Disconnected all active hardware resources."
            if not errors
            else "Disconnected available resources, but some disconnect operations failed."
        ),
        "results": results,
        "errors": errors,
    }
