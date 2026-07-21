from __future__ import annotations

from ..mcp_execution import SessionToolRegistrar
from ..session import SessionState
from ..tool_profiles import ToolProfile, resolve_tool_profile
from .build_debug import register_build_debug_tools
from .diagnostics import register_diagnostic_tools
from .evidence import register_evidence_tools
from .io import register_io_tools
from .probe import register_probe_tools
from .runtime import register_runtime_tools
from .svd import register_svd_tools


def register_all_tools(
    mcp,
    session: SessionState,
    *,
    tool_profile: ToolProfile | None = None,
) -> None:
    registrar = SessionToolRegistrar(
        mcp,
        session,
        tool_profile=tool_profile or resolve_tool_profile(),
    )
    register_runtime_tools(registrar, session)
    register_build_debug_tools(registrar, session)
    register_probe_tools(registrar, session)
    register_evidence_tools(registrar, session)
    register_io_tools(registrar, session)
    register_svd_tools(registrar, session)
    register_diagnostic_tools(registrar, session)
