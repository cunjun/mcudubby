from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from .session import SessionState


CONCURRENT_TOOL_NAMES = frozenset(
    {
        "discover_keil_projects",
        "get_target_info",
        "list_demo_profiles",
        "list_supported_targets",
        "list_tool_safety",
        "list_validation_records",
        "match_chip_name",
    }
)


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
                if callback.__name__ in CONCURRENT_TOOL_NAMES:
                    return await asyncio.to_thread(_run_callback, callback, args, kwargs)
                return await _run_serialized(self._session, callback, args, kwargs)

            return register(execute)

        return decorate
