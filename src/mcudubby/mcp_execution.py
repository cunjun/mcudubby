from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from .session import SessionState
from .tool_safety import get_tool_safety, require_tool_confirmation


def _run_callback(callback: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    result = callback(*args, **kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


async def _run_serialized(
    session: SessionState,
    callback: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    async with session.execution_lock:
        worker = asyncio.create_task(asyncio.to_thread(_run_callback, callback, args, kwargs))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            try:
                await worker
            except Exception:
                pass
            raise


class SessionToolRegistrar:
    """Register MCP tools behind a worker-thread and session-serialization boundary."""

    def __init__(self, mcp: Any, session: SessionState) -> None:
        self._mcp = mcp
        self._session = session

    def tool(self, *decorator_args: Any, **decorator_kwargs: Any) -> Callable:
        register = self._mcp.tool(*decorator_args, **decorator_kwargs)

        def decorate(callback: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(callback)
            async def execute(*args: Any, **kwargs: Any) -> Any:
                policy = get_tool_safety(callback.__name__)
                bound = inspect.signature(callback).bind_partial(*args, **kwargs)
                confirmed = bool(bound.arguments.get("confirm", False))
                if blocked := require_tool_confirmation(callback.__name__, confirmed):
                    return blocked
                if policy["execution"] == "concurrent":
                    return await asyncio.to_thread(_run_callback, callback, args, kwargs)
                return await _run_serialized(self._session, callback, args, kwargs)

            return register(execute)

        return decorate
