"""Tests for SVD peripheral register tools."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock

import pytest

from mcudubby.svd_manager import SvdManager


# ---------------------------------------------------------------------------
# Minimal in-memory SVD XML for testing
# ---------------------------------------------------------------------------

_MINIMAL_SVD = """\
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
            <field>
              <name>UE</name>
              <bitOffset>13</bitOffset>
              <bitWidth>1</bitWidth>
              <description>USART enable</description>
            </field>
            <field>
              <name>TE</name>
              <bitOffset>3</bitOffset>
              <bitWidth>1</bitWidth>
              <description>Transmitter enable</description>
            </field>
            <field>
              <name>RE</name>
              <bitOffset>2</bitOffset>
              <bitWidth>1</bitWidth>
              <description>Receiver enable</description>
            </field>
          </fields>
        </register>
        <register>
          <name>BRR</name>
          <addressOffset>0xC</addressOffset>
          <description>Baud rate register</description>
          <fields>
            <field>
              <name>BRR</name>
              <bitOffset>0</bitOffset>
              <bitWidth>16</bitWidth>
              <description>Baud rate</description>
            </field>
          </fields>
        </register>
      </registers>
    </peripheral>
    <peripheral>
      <name>GPIOA</name>
      <baseAddress>0x48000000</baseAddress>
      <registers>
        <register>
          <name>MODER</name>
          <addressOffset>0x0</addressOffset>
          <description>Mode register</description>
          <fields>
            <field>
              <name>MODER0</name>
              <bitOffset>0</bitOffset>
              <bitWidth>2</bitWidth>
              <description>Pin 0 mode</description>
            </field>
          </fields>
        </register>
        <register>
          <name>ODR</name>
          <addressOffset>0x14</addressOffset>
          <description>Output data register</description>
          <fields>
            <field>
              <name>OD0</name>
              <bitOffset>0</bitOffset>
              <bitWidth>1</bitWidth>
              <description>Pin 0 output</description>
            </field>
          </fields>
        </register>
        <register>
          <name>IDR</name>
          <addressOffset>0x10</addressOffset>
          <description>Input data register</description>
          <fields>
            <field>
              <name>ID0</name>
              <bitOffset>0</bitOffset>
              <bitWidth>1</bitWidth>
              <description>Pin 0 input</description>
            </field>
          </fields>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""


@pytest.fixture()
def svd_file(tmp_path):
    f = tmp_path / "test.svd"
    f.write_text(_MINIMAL_SVD, encoding="utf-8")
    return str(f)


@pytest.fixture()
def manager(svd_file):
    mgr = SvdManager()
    result = mgr.load(svd_file)
    assert result["status"] == "ok"
    return mgr


# ---------------------------------------------------------------------------
# Load tests
# ---------------------------------------------------------------------------


def test_load_returns_ok(svd_file):
    mgr = SvdManager()
    result = mgr.load(svd_file)
    assert result["status"] == "ok"
    assert mgr.is_loaded
    assert result["peripheral_count"] == 2


def test_load_missing_file():
    mgr = SvdManager()
    result = mgr.load("/nonexistent/path/device.svd")
    assert result["status"] == "error"
    assert "not found" in result["summary"]


# ---------------------------------------------------------------------------
# List peripherals
# ---------------------------------------------------------------------------


def test_list_peripherals(manager):
    result = manager.list_peripherals()
    assert result["status"] == "ok"
    names = [p["name"] for p in result["peripherals"]]
    assert "USART2" in names
    assert "GPIOA" in names


def test_list_peripherals_not_loaded():
    mgr = SvdManager()
    result = mgr.list_peripherals()
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Get register layout
# ---------------------------------------------------------------------------


def test_get_registers_usart2(manager):
    result = manager.get_peripheral_registers("USART2")
    assert result["status"] == "ok"
    assert result["peripheral"] == "USART2"
    assert result["base_address"] == hex(0x40004400)
    reg_names = [r["name"] for r in result["registers"]]
    assert "CR1" in reg_names
    assert "BRR" in reg_names


def test_get_registers_case_insensitive(manager):
    result = manager.get_peripheral_registers("usart2")
    assert result["status"] == "ok"
    assert result["peripheral"] == "USART2"


def test_get_registers_unknown_peripheral(manager):
    result = manager.get_peripheral_registers("I2C1")
    assert result["status"] == "error"
    assert "suggestions" in result


def test_cr1_fields_present(manager):
    result = manager.get_peripheral_registers("USART2")
    cr1 = next(r for r in result["registers"] if r["name"] == "CR1")
    field_names = [f["name"] for f in cr1["fields"]]
    assert "UE" in field_names
    assert "TE" in field_names
    assert "RE" in field_names


# ---------------------------------------------------------------------------
# Read peripheral state (with mock probe)
# ---------------------------------------------------------------------------


def _make_mock_probe(memory: dict[int, int]) -> MagicMock:
    """Create a mock probe that returns bytes for read_memory calls."""
    probe = MagicMock()

    def read_memory(address, size):
        value = memory.get(address, 0)
        return struct.pack("<I", value)[:size]

    probe.read_memory.side_effect = read_memory
    return probe


def test_read_peripheral_usart_disabled(manager):
    # CR1=0x00000000 (all disabled), BRR=0x0683 (115200 @ 160MHz)
    probe = _make_mock_probe(
        {
            0x40004400: 0x00000000,  # CR1: UE=0, TE=0, RE=0
            0x4000440C: 0x00000683,  # BRR
        }
    )
    result = manager.read_peripheral_state("USART2", probe)
    assert result["status"] == "ok"
    # Diagnosis should note that USART is disabled
    diag_text = " ".join(result["diagnosis"])
    assert "disabled" in diag_text.lower() or "UE=0" in diag_text


def test_read_peripheral_usart_enabled(manager):
    # CR1 = UE(bit13)=1, TE(bit3)=1, RE(bit2)=1 - 0x0000200C
    probe = _make_mock_probe(
        {
            0x40004400: 0x0000200C,
            0x4000440C: 0x00000683,
        }
    )
    result = manager.read_peripheral_state("USART2", probe)
    assert result["status"] == "ok"
    cr1 = next(r for r in result["registers"] if r["name"] == "CR1")
    field_map = {f["name"]: f["value"] for f in cr1["fields"]}
    assert field_map["UE"] == 1
    assert field_map["TE"] == 1
    assert field_map["RE"] == 1


def test_read_peripheral_field_extraction(manager):
    # BRR = 0x0683
    probe = _make_mock_probe(
        {
            0x40004400: 0x00000000,
            0x4000440C: 0x00000683,
        }
    )
    result = manager.read_peripheral_state("USART2", probe)
    brr_reg = next(r for r in result["registers"] if r["name"] == "BRR")
    assert brr_reg["value"] == hex(0x683)


def test_read_peripheral_not_found(manager):
    probe = _make_mock_probe({})
    result = manager.read_peripheral_state("I2C3", probe)
    assert result["status"] == "error"
