from __future__ import annotations

import asyncio
import threading
import time

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcudubby.server import create_server
from mcudubby.session import SessionState


class _BlockingProbe:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds
        self.active_calls = 0
        self.max_active_calls = 0
        self.disconnect_overlapped = False
        self._state_lock = threading.Lock()

    def halt(self) -> dict:
        with self._state_lock:
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            time.sleep(self.delay_seconds)
            return {"status": "ok", "summary": "halted"}
        finally:
            with self._state_lock:
                self.active_calls -= 1

    def resume(self) -> dict:
        return self.halt()

    def disconnect(self) -> dict:
        with self._state_lock:
            self.disconnect_overlapped = self.active_calls > 0
        return {"status": "ok", "summary": "disconnected"}


class _ControlledProbe(_BlockingProbe):
    def __init__(self) -> None:
        super().__init__(delay_seconds=0)
        self.started = threading.Event()
        self.release = threading.Event()

    def halt(self) -> dict:
        with self._state_lock:
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
            self.started.set()
        try:
            if not self.release.wait(timeout=5):
                raise TimeoutError("test probe was not released")
            return {"status": "ok", "summary": "halted"}
        finally:
            with self._state_lock:
                self.active_calls -= 1


class _FailingProbe(_BlockingProbe):
    def __init__(self) -> None:
        super().__init__(delay_seconds=0)

    def halt(self) -> dict:
        raise RuntimeError("probe failed")

    def resume(self) -> dict:
        return {"status": "ok", "summary": "resumed"}


async def _run_tool(app, name: str, arguments: dict | None = None):
    tool = app._tool_manager.get_tool(name)
    return await tool.run(arguments or {})


def test_execution_boundary_preserves_tool_registration_contract() -> None:
    app = create_server(SessionState())

    assert len(app._tool_manager._tools) == 104
    assert app._tool_manager.get_tool("probe_reset").parameters == {
        "properties": {
            "halt": {"default": False, "title": "Halt", "type": "boolean"},
        },
        "title": "probe_resetArguments",
        "type": "object",
    }


def test_blocking_session_tool_does_not_block_metadata_query() -> None:
    async def scenario() -> bool:
        session = SessionState()
        probe = _ControlledProbe()
        session.probe = probe
        app = create_server(session)

        halt_task = asyncio.create_task(_run_tool(app, "probe_halt"))
        assert await asyncio.to_thread(probe.started.wait, 1)
        try:
            await asyncio.wait_for(_run_tool(app, "list_tool_safety"), timeout=1)
            return not halt_task.done()
        finally:
            probe.release.set()
            await halt_task

    assert asyncio.run(scenario()) is True


def test_different_sessions_can_execute_blocking_tools_in_parallel() -> None:
    async def scenario() -> tuple[int, int]:
        first_session = SessionState()
        first_probe = _ControlledProbe()
        first_session.probe = first_probe
        second_session = SessionState()
        second_probe = _ControlledProbe()
        second_session.probe = second_probe
        first_app = create_server(first_session)
        second_app = create_server(second_session)

        first_task = asyncio.create_task(_run_tool(first_app, "probe_halt"))
        second_task = asyncio.create_task(_run_tool(second_app, "probe_halt"))
        try:
            started = await asyncio.gather(
                asyncio.to_thread(first_probe.started.wait, 1),
                asyncio.to_thread(second_probe.started.wait, 1),
            )
            assert all(started)
            return first_probe.active_calls, second_probe.active_calls
        finally:
            first_probe.release.set()
            second_probe.release.set()
            await asyncio.gather(first_task, second_task)

    assert asyncio.run(scenario()) == (1, 1)


def test_same_session_serializes_blocking_tools() -> None:
    async def scenario() -> int:
        session = SessionState()
        probe = _BlockingProbe(delay_seconds=0.05)
        session.probe = probe
        app = create_server(session)

        await asyncio.gather(
            _run_tool(app, "probe_halt"),
            _run_tool(app, "probe_halt"),
        )
        return probe.max_active_calls

    assert asyncio.run(scenario()) == 1


def test_execution_boundary_applies_to_other_session_tools() -> None:
    async def scenario() -> bool:
        session = SessionState()
        probe = _ControlledProbe()
        session.probe = probe
        app = create_server(session)

        resume_task = asyncio.create_task(_run_tool(app, "probe_resume"))
        assert await asyncio.to_thread(probe.started.wait, 1)
        try:
            await asyncio.wait_for(_run_tool(app, "list_tool_safety"), timeout=1)
            return not resume_task.done()
        finally:
            probe.release.set()
            await resume_task

    assert asyncio.run(scenario()) is True


def test_cancellation_keeps_session_locked_until_worker_finishes() -> None:
    async def scenario() -> int:
        session = SessionState()
        probe = _ControlledProbe()
        session.probe = probe
        app = create_server(session)

        first = asyncio.create_task(_run_tool(app, "probe_halt"))
        assert await asyncio.to_thread(probe.started.wait, 0.5)
        first.cancel()
        await asyncio.sleep(0)

        second = asyncio.create_task(_run_tool(app, "probe_resume"))
        await asyncio.sleep(0)
        overlapping_calls = probe.max_active_calls
        probe.release.set()

        with pytest.raises(asyncio.CancelledError):
            await first
        await second
        return overlapping_calls

    assert asyncio.run(scenario()) == 1


def test_session_lock_is_released_after_worker_error() -> None:
    async def scenario() -> dict:
        session = SessionState()
        session.probe = _FailingProbe()
        app = create_server(session)

        with pytest.raises(ToolError, match="probe failed"):
            await _run_tool(app, "probe_halt")
        return await asyncio.wait_for(_run_tool(app, "probe_resume"), timeout=0.5)

    assert asyncio.run(scenario())["status"] == "ok"


def test_backend_switch_waits_for_active_session_operation(monkeypatch) -> None:
    replacement = _BlockingProbe(delay_seconds=0)
    monkeypatch.setattr(
        "mcudubby.tools.configuration.create_probe_backend",
        lambda *args, **kwargs: replacement,
    )

    async def scenario() -> bool:
        session = SessionState()
        current = _ControlledProbe()
        session.probe = current
        app = create_server(session)

        halt = asyncio.create_task(_run_tool(app, "probe_halt"))
        assert await asyncio.to_thread(current.started.wait, 0.5)
        configure = asyncio.create_task(
            _run_tool(app, "configure_probe", {"backend": "probe-rs"})
        )
        await asyncio.sleep(0.05)
        current.release.set()
        await halt
        result = await configure
        assert result["status"] == "ok"
        return current.disconnect_overlapped

    assert asyncio.run(scenario()) is False
