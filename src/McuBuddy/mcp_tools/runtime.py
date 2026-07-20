from __future__ import annotations

from ..session import SessionState
from ..tool_safety import list_tool_safety as _list_tool_safety
from ..validation_records import list_validation_records as _list_validation_records
from ..tools.configuration import configure_build as _configure_build
from ..tools.configuration import configure_elf as _configure_elf
from ..tools.configuration import configure_log as _configure_log
from ..tools.configuration import configure_probe as _configure_probe
from ..tools.configuration import connect_with_config as _connect_with_config
from ..tools.configuration import get_runtime_config as _get_runtime_config
from ..tools.configuration import get_target_info as _get_target_info
from ..tools.configuration import list_demo_profiles as _list_demo_profiles
from ..tools.configuration import list_supported_targets as _list_supported_targets
from ..tools.configuration import load_demo_profile as _load_demo_profile
from ..tools.configuration import match_chip_name as _match_chip_name
from ..tools.debug_loop import run_debug_loop as _run_debug_loop
from ..tools.project import configure_keil_project as _configure_keil_project
from ..tools.project import discover_keil_projects as _discover_keil_projects
from ..tools.smoke import board_smoke_test as _board_smoke_test
from ..tools.smoke import doctor as _doctor
from ..tools.smoke import first_contact as _first_contact


def register_runtime_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def get_runtime_config() -> dict:
        return _get_runtime_config(session)

    @mcp.tool()
    async def list_demo_profiles() -> dict:
        return _list_demo_profiles()

    @mcp.tool()
    async def load_demo_profile(profile_name: str) -> dict:
        return _load_demo_profile(session, profile_name=profile_name)

    @mcp.tool()
    async def match_chip_name(target: str, backend: str = "pyocd") -> dict:
        """Resolve a chip alias to a backend-specific target name."""
        return _match_chip_name(target=target, backend=backend)

    @mcp.tool()
    async def get_target_info(target: str, backend: str = "pyocd") -> dict:
        """Return alias-match and device-patch info for a target on a given backend."""
        return _get_target_info(target=target, backend=backend)

    @mcp.tool()
    async def list_supported_targets(backend: str | None = None) -> dict:
        """List built-in target profiles and validation metadata for a backend."""
        return _list_supported_targets(backend=backend)

    @mcp.tool()
    async def list_tool_safety() -> dict:
        """List safety levels for public McuBuddy tools."""
        return _list_tool_safety()

    @mcp.tool()
    async def list_validation_records() -> dict:
        """List machine-readable real-hardware validation records."""
        return _list_validation_records()

    @mcp.tool()
    async def configure_probe(
        target: str | None = None,
        unique_id: str | None = None,
        backend: str | None = None,
        jlink_dll_path: str | None = None,
        probe_rs_sidecar_path: str | None = None,
        pack_path: str | None = None,
        pack_paths: list[str] | None = None,
        connect_attempts: list[dict[str, object]] | None = None,
    ) -> dict:
        """Set probe connection parameters. Run list_connected_probes first to find unique_id."""
        return _configure_probe(
            session,
            target=target,
            unique_id=unique_id,
            backend=backend,
            jlink_dll_path=jlink_dll_path,
            probe_rs_sidecar_path=probe_rs_sidecar_path,
            pack_path=pack_path,
            pack_paths=pack_paths,
            connect_attempts=connect_attempts,
        )

    @mcp.tool()
    async def configure_log(uart_port: str | None = None, uart_baudrate: int | None = None) -> dict:
        """Set UART log channel parameters (e.g. uart_port='COM5', uart_baudrate=115200)."""
        return _configure_log(session, uart_port=uart_port, uart_baudrate=uart_baudrate)

    @mcp.tool()
    async def configure_elf(elf_path: str) -> dict:
        """Set the ELF/AXF file path for symbol resolution."""
        return _configure_elf(session, elf_path=elf_path)

    @mcp.tool()
    async def configure_build(
        uv4_path: str | None = None,
        project_path: str | None = None,
        target_name: str | None = None,
        build_log_path: str | None = None,
        flash_log_path: str | None = None,
    ) -> dict:
        """Set Keil UV4 build/flash parameters. Only needed if using build_project or flash_firmware."""
        return _configure_build(
            session,
            uv4_path=uv4_path,
            project_path=project_path,
            target_name=target_name,
            build_log_path=build_log_path,
            flash_log_path=flash_log_path,
        )

    @mcp.tool()
    async def discover_keil_projects(root: str, max_depth: int = 6) -> dict:
        """Find Keil project files, targets, and likely AXF/ELF outputs under a directory."""
        return _discover_keil_projects(root=root, max_depth=max_depth)

    @mcp.tool()
    async def configure_keil_project(
        root: str | None = None,
        project_path: str | None = None,
        uv4_path: str | None = None,
        target_name: str | None = None,
        elf_path: str | None = None,
        build_log_path: str | None = None,
        flash_log_path: str | None = None,
    ) -> dict:
        """Auto-configure Keil build and ELF paths from a project path or discovery root."""
        return _configure_keil_project(
            session,
            root=root,
            project_path=project_path,
            uv4_path=uv4_path,
            target_name=target_name,
            elf_path=elf_path,
            build_log_path=build_log_path,
            flash_log_path=flash_log_path,
        )

    @mcp.tool()
    async def connect_with_config() -> dict:
        return _connect_with_config(session)

    @mcp.tool()
    async def doctor() -> dict:
        """Run a read-only environment, dependency, probe, target, and config preflight."""
        return _doctor(session)

    @mcp.tool()
    async def board_smoke_test(
        target: str | None = None,
        unique_id: str | None = None,
        load_elf: bool = True,
        halt: bool = True,
        read_vectors: bool = True,
        vector_address: int = 0x08000000,
        vector_words: int = 4,
        disconnect_after: bool = False,
    ) -> dict:
        """Run a generic read-only hardware sanity check for the configured board."""
        return _board_smoke_test(
            session,
            target=target,
            unique_id=unique_id,
            load_elf=load_elf,
            halt=halt,
            read_vectors=read_vectors,
            vector_address=vector_address,
            vector_words=vector_words,
            disconnect_after=disconnect_after,
        )

    @mcp.tool()
    async def first_contact(
        target: str,
        backend: str = "pyocd",
        unique_id: str | None = None,
        elf_path: str | None = None,
        pack_path: str | None = None,
        pack_paths: list[str] | None = None,
        disconnect_after: bool = True,
    ) -> dict:
        """Run the safest first board contact flow and suggest next debug tools."""
        return _first_contact(
            session,
            target=target,
            backend=backend,
            unique_id=unique_id,
            elf_path=elf_path,
            pack_path=pack_path,
            pack_paths=pack_paths,
            disconnect_after=disconnect_after,
        )

    @mcp.tool()
    async def run_debug_loop(
        issue_description: str,
        profile_name: str | None = None,
        build_before_debug: bool = False,
        flash_before_debug: bool = False,
        confirm_flash_before_debug: bool = False,
        log_tail_lines: int = 30,
        suspected_stage: str | None = None,
    ) -> dict:
        return _run_debug_loop(
            session,
            issue_description=issue_description,
            profile_name=profile_name,
            build_before_debug=build_before_debug,
            flash_before_debug=flash_before_debug,
            confirm_flash_before_debug=confirm_flash_before_debug,
            log_tail_lines=log_tail_lines,
            suspected_stage=suspected_stage,
        )
