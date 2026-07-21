from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from .session import SessionState
from .tool_safety import get_tool_safety, require_tool_confirmation
from .tool_profiles import ToolProfile, resolve_tool_profile


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

    def __init__(
        self,
        mcp: Any,
        session: SessionState,
        *,
        tool_profile: ToolProfile | None = None,
    ) -> None:
        self._mcp = mcp
        self._session = session
        self._tool_profile = tool_profile or resolve_tool_profile()

    @property
    def active_tool_profile(self) -> ToolProfile:
        return self._tool_profile

    def tool(self, *decorator_args: Any, **decorator_kwargs: Any) -> Callable:
        def decorate(callback: Callable[..., Any]) -> Callable[..., Any]:
            if not self._tool_profile.allows(callback.__name__):
                return callback

            register = self._mcp.tool(*decorator_args, **decorator_kwargs)

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
