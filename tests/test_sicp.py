"""Tests du client SICP (framing, ACK/NAV/NACK)."""
import pytest

from custom_components.philips_dline_sicp.sicp import PhilipsSICP, SICPNACKError, SICPNAVError

from . import fake_monitor


def test_build_packet_matches_spec():
    client = PhilipsSICP("127.0.0.1")
    # Exemples de la spécification SICP 2.09
    assert client.build_packet(0x19).hex(" ") == "05 01 00 19 1d"
    assert client.build_packet(0xAC, bytes([0x0D, 0x09, 0x01, 0x00])).hex(" ") == "09 01 00 ac 0d 09 01 00 a1"
    assert client.build_packet(0x44, bytes([0x16, 0x32])).hex(" ") == "07 01 00 44 16 32 66"
    no_group = PhilipsSICP("127.0.0.1", include_group=False)
    assert no_group.build_packet(0x19).hex(" ") == "04 01 19 1c"


async def test_get_and_set(monitor):
    client = PhilipsSICP("127.0.0.1", port=monitor)
    assert await client.async_get_power() is True
    assert await client.async_get(0x33) == bytes([55, 50, 45, 5, 50, 50, 3])
    await client.async_set_volume(40)
    assert fake_monitor.STATE[0x45] == bytes([40, 20])  # sortie audio inchangée (0xFF)
    assert await client.async_get_sources() == [0x0D, 0x06, 0x0A, 0x16]
    assert await client.async_get_text(0xA1, b"\x00") == "43BDL4550D/00"
    await client.disconnect()


async def test_nack_and_nav(monitor):
    client = PhilipsSICP("127.0.0.1", port=monitor)
    with pytest.raises(SICPNACKError):
        await client.async_get(0xE3, b"\x01")
    await client.async_set_power(False)
    with pytest.raises(SICPNAVError):
        await client.async_get(0x33)
    await client.disconnect()
