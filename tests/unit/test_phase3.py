"""Tests for Phase 3 symptom-driven peripheral diagnosis."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock

import pytest

from McuBuddy.svd_manager import SvdManager
from McuBuddy.tools.phase3 import diagnose_peripheral_stuck


# ---------------------------------------------------------------------------
# Minimal SVD: USART2 + RCC with APB1ENR1 (USART2EN at bit 17)
# ---------------------------------------------------------------------------

_SVD = """\
<?xml version="1.0" encoding="utf-8"?>
<device>
  <name>TEST_MCU</name>
  <version>1.0</version>
  <addressUnitBits>8</addressUnitBits>
  <width>32</width>
  <peripherals>
    <peripheral>
      <name>USART2</name>
      <baseAddress>0x40004400</baseAddress>
      <registers>
        <register>
          <name>CR1</name>
          <addressOffset>0x0</addressOffset>
          <description>Control register 1</description>
          <fields>
            <field><name>UE</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth><description>USART enable</description></field>
            <field><name>TE</name><bitOffset>3</bitOffset><bitWidth>1</bitWidth><description>Transmitter enable</description></field>
            <field><name>RE</name><bitOffset>2</bitOffset><bitWidth>1</bitWidth><description>Receiver enable</description></field>
          </fields>
        </register>
      </registers>
    </peripheral>
    <peripheral>
      <name>RCC</name>
      <baseAddress>0x40021000</baseAddress>
      <registers>
        <register>
          <name>APB1ENR1</name>
          <addressOffset>0x58</addressOffset>
          <description>APB1 peripheral clock enable register 1</description>
          <fields>
            <field><name>USART2EN</name><bitOffset>17</bitOffset><bitWidth>1</bitWidth><description>USART2 clock enable</description></field>
            <field><name>USART3EN</name><bitOffset>18</bitOffset><bitWidth>1</bitWidth><description>USART3 clock enable</description></field>
          </fields>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""

_RCC_APB1ENR1_ADDR = 0x40021000 + 0x58
_USART2_CR1_ADDR = 0x40004400


@pytest.fixture()
def svd_file(tmp_path):
    f = tmp_path / "test.svd"
    f.write_text(_SVD, encoding="utf-8")
    return str(f)


def _make_session(svd_file: str, memory: dict[int, int]):
    """Create a minimal session-like object with SVD loaded and mock probe."""
    svd = SvdManager()
    svd.load(svd_file)

    probe = MagicMock()

    def read_memory(addr, size):
        return struct.pack("<I", memory.get(addr, 0))[:size]

    probe.read_memory.side_effect = read_memory

    session = MagicMock()
    session.svd = svd
    session.probe = probe
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_rcc_clock_disabled(svd_file):
    session = _make_session(
        svd_file,
        {
            _USART2_CR1_ADDR: 0x0,
            _RCC_APB1ENR1_ADDR: 0x0,  # USART2EN=0
        },
    )
    result = diagnose_peripheral_stuck(session, "USART2", symptom="no output")
    assert result["status"] == "ok"
    rcc_text = " ".join(result["rcc_notes"])
    assert "NOT enabled" in rcc_text


def test_rcc_clock_enabled(svd_file):
    session = _make_session(
        svd_file,
        {
            _USART2_CR1_ADDR: 0x0000200D,  # UE+TE+RE set
            _RCC_APB1ENR1_ADDR: 1 << 17,  # USART2EN=1
        },
    )
    result = diagnose_peripheral_stuck(session, "USART2")
    assert result["status"] == "ok"
    rcc_text = " ".join(result["rcc_notes"])
    assert "NOT enabled" not in rcc_text
    assert "enabled" in rcc_text.lower()


def test_svd_not_loaded():
    session = MagicMock()
    session.svd.is_loaded = False
    result = diagnose_peripheral_stuck(session, "USART2")
    assert result["status"] == "error"
    assert "SVD" in result["summary"]


def test_evidence_combines_diagnosis_and_rcc(svd_file):
    session = _make_session(
        svd_file,
        {
            _USART2_CR1_ADDR: 0x0,
            _RCC_APB1ENR1_ADDR: 0x0,
        },
    )
    result = diagnose_peripheral_stuck(session, "USART2", symptom="silent TX")
    assert result["symptom"] == "silent TX"
    assert len(result["evidence"]) >= 2  # at least one diagnosis + one RCC note
    assert result["diagnosis"]
    assert result["rcc_notes"]


def test_unknown_peripheral_returns_error(svd_file):
    """read_peripheral_state returns error for unknown peripheral - verify it propagates."""
    session = _make_session(svd_file, {})
    result = diagnose_peripheral_stuck(session, "I2C99")
    assert result["status"] == "error"
    assert "summary" in result


def test_probe_not_connected(svd_file):
    """Probe that raises on read_memory should report probe not connected."""
    svd = SvdManager()
    svd.load(svd_file)

    probe = MagicMock()
    probe.read_memory.side_effect = RuntimeError("no probe")

    session = MagicMock()
    session.svd = svd
    session.probe = probe

    result = diagnose_peripheral_stuck(session, "USART2")
    assert result["status"] == "error"
    assert "Probe" in result["summary"]


def test_no_matching_rcc_clock_field(svd_file):
    """RCC is present in SVD but has no *EN field matching the peripheral name."""
    # "RCC" itself is in the SVD; searching for "RCCE" in RCC registers will
    # find nothing, exercising the "No clock-enable bit found" fallback path.
    session = _make_session(
        svd_file,
        {
            _RCC_APB1ENR1_ADDR: 0x0,
            0x40021000: 0x0,  # RCC base (CR register at offset 0)
        },
    )
    result = diagnose_peripheral_stuck(session, "RCC")
    assert result["status"] == "ok"
    rcc_text = " ".join(result["rcc_notes"])
    assert "No clock-enable bit found" in rcc_text


def test_rcc_register_read_failure(svd_file):
    """Probe raises when reading the RCC register; error should appear in rcc_notes."""
    _CORTEX_M_SCS = 0xE000E000
    _USART2_CR1 = _USART2_CR1_ADDR

    def read_memory(addr, size):
        if addr == _RCC_APB1ENR1_ADDR:
            raise OSError("bus error on RCC")
        return struct.pack("<I", {_CORTEX_M_SCS: 0x0, _USART2_CR1: 0x0}.get(addr, 0))[:size]

    svd = SvdManager()
    svd.load(svd_file)
    probe = MagicMock()
    probe.read_memory.side_effect = read_memory

    session = MagicMock()
    session.svd = svd
    session.probe = probe

    result = diagnose_peripheral_stuck(session, "USART2")
    assert result["status"] == "ok"
    rcc_text = " ".join(result["rcc_notes"])
    assert "Failed to read RCC register" in rcc_text
