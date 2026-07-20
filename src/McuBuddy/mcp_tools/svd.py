from __future__ import annotations

from ..session import SessionState
from ..tools.svd import svd_get_registers as _svd_get_registers
from ..tools.svd import svd_list_peripherals as _svd_list_peripherals
from ..tools.svd import svd_load as _svd_load
from ..tools.svd import svd_read_peripheral as _svd_read_peripheral
from ..tools.svd import svd_write_field as _svd_write_field
from ..tools.svd import svd_write_register as _svd_write_register


def register_svd_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def svd_load(svd_path: str) -> dict:
        """Load a CMSIS-SVD file to enable peripheral register interpretation.

        SVD files define the register map of a chip. You can find SVD files
        in your chip vendor's SDK, or at https://github.com/posborne/cmsis-svd-data
        Example: svd_load('/path/to/STM32L496.svd')
        """
        return _svd_load(session, svd_path=svd_path)

    @mcp.tool()
    async def svd_list_peripherals() -> dict:
        """List all peripherals in the loaded SVD (UART, SPI, I2C, GPIO, TIM, etc.)."""
        return _svd_list_peripherals(session)

    @mcp.tool()
    async def svd_get_registers(peripheral: str) -> dict:
        """Return the register layout for a peripheral without reading hardware.

        Useful to understand what registers and fields exist before reading values.
        Example: svd_get_registers('USART2')
        """
        return _svd_get_registers(session, peripheral=peripheral)

    @mcp.tool()
    async def svd_read_peripheral(peripheral: str) -> dict:
        """Read all register values for a peripheral and interpret each field.

        Combines hardware register reads with SVD field definitions to produce
        a structured, human-readable view of peripheral state.
        Requires probe connected and target halted.
        Example: svd_read_peripheral('USART2')
        """
        return _svd_read_peripheral(session, peripheral=peripheral)

    @mcp.tool()
    async def svd_write_register(
        peripheral: str,
        register: str,
        value: int,
        confirm: bool = False,
    ) -> dict:
        """Write a 32-bit value to a peripheral register by name using SVD addressing.

        Looks up the register address from the loaded SVD, then writes the value.
        Requires SVD loaded and probe connected.
        Example: svd_write_register('USART2', 'CR1', 0x000C)
        Example: svd_write_register('GPIOA', 'ODR', 0x0001)
        """
        return _svd_write_register(
            session,
            peripheral=peripheral,
            register=register,
            value=value,
            confirm=confirm,
        )

    @mcp.tool()
    async def svd_write_field(
        peripheral: str,
        register: str,
        field: str,
        value: int,
        confirm: bool = False,
    ) -> dict:
        """Write a value to a single bit-field in a peripheral register (read-modify-write).

        Reads the current register value, updates only the target field bits, writes back.
        Safer than svd_write_register when you only want to change one field.
        Example: svd_write_field('RCC', 'CR', 'PLLON', 1)
        Example: svd_write_field('GPIOA', 'MODER', 'MODER5', 2)
        """
        return _svd_write_field(
            session,
            peripheral=peripheral,
            register=register,
            field=field,
            value=value,
            confirm=confirm,
        )
