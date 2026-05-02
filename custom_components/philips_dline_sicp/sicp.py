"""Philips SICP protocol client over TCP."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

_LOGGER = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# SICP command bytes (common D-Line commands)
# ──────────────────────────────────────────────
CMD_POWER_GET    = 0x19
CMD_POWER_SET    = 0x18
CMD_INPUT_GET    = 0xAD
CMD_INPUT_SET    = 0xAC
CMD_VOLUME_GET   = 0x45
CMD_VOLUME_SET   = 0x44
CMD_MUTE_GET     = 0xAB
CMD_MUTE_SET     = 0x47
CMD_BRIGHT_GET   = 0x33
CMD_BRIGHT_SET   = 0x32
CMD_CONTRAST_GET = 0x13
CMD_CONTRAST_SET = 0x12

# Input source codes (D-Line firmware defaults)
INPUT_CODES = {
    "HDMI 1":        0x0D,
    "HDMI 2":        0x06,
    "HDMI 3":        0x0F,
    "HDMI 4":        0x19,
    "DisplayPort":   0x22,
    "DVI-D":         0x04,
    "VGA":           0x01,
    "Media Player":  0x30,
    "Browser":       0x40,
    "PDF Player":    0x41,
    "Card OPS":      0x07,
}
INPUT_CODES_INV = {v: k for k, v in INPUT_CODES.items()}

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT    = 1.5


class SICPError(Exception):
    """Base SICP error."""


class SICPConnectError(SICPError):
    """Cannot connect to display."""


class SICPTimeoutError(SICPError):
    """No reply in time."""


class SICPNACKError(SICPError):
    """Display replied NACK (checksum error)."""


class PhilipsSICP:
    """Async SICP client. Creates a new TCP connection for each command."""

    def __init__(
        self,
        host: str,
        port: int = 5000,
        monitor_id: int = 1,
        group_id: int = 0,
        include_group: bool = True,
    ) -> None:
        self.host         = host
        self.port         = port
        self.monitor_id   = monitor_id
        self.group_id     = group_id
        self.include_group = include_group

    # ──────────────────────────────────────────
    # Internal framing helpers
    # ──────────────────────────────────────────

    def _build_packet(self, command: int, data: bytes = b"") -> bytes:
        """Build a SICP packet.

        Format (v2):
          [len] [monitor_id] [group_id?] [cmd] [data…] [checksum]
          len = total packet length including len byte and checksum byte
        """
        if self.include_group:
            header = bytes([self.monitor_id, self.group_id, command])
        else:
            header = bytes([self.monitor_id, command])

        # Length = 1 (len byte) + header + data + 1 (checksum)
        body = header + data
        length = len(body) + 2  # +1 len itself +1 checksum
        packet = bytes([length]) + body
        checksum = 0
        for b in packet:
            checksum ^= b
        return packet + bytes([checksum])

    def _parse_reply(self, raw: bytes) -> bytes:
        """Return the data portion of an ACK reply, or raise."""
        if len(raw) < 3:
            raise SICPError(f"Reply too short: {raw.hex()}")

        # Verify checksum
        chk = 0
        for b in raw[:-1]:
            chk ^= b
        if chk != raw[-1]:
            raise SICPNACKError("Checksum mismatch in reply")

        # ACK byte is at position 3 (after len, id, group if present)
        # We simply return the payload starting after the command byte.
        if self.include_group:
            # reply: [len][id][group][cmd_echo][ack/data…][chk]
            payload = raw[4:-1]
        else:
            payload = raw[3:-1]

        return payload

    async def _send(self, command: int, data: bytes = b"") -> bytes:
        """Open connection, send packet, read reply."""
        packet = self._build_packet(command, data)
        _LOGGER.debug("SICP → %s", packet.hex())

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=CONNECT_TIMEOUT,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise SICPConnectError(f"Cannot connect to {self.host}:{self.port}: {exc}") from exc

        try:
            writer.write(packet)
            await writer.drain()

            reply = await asyncio.wait_for(reader.read(64), timeout=READ_TIMEOUT)
            _LOGGER.debug("SICP ← %s", reply.hex())

            if not reply:
                raise SICPTimeoutError("Empty reply from display")

            return self._parse_reply(reply)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    async def async_get_power(self) -> bool:
        """Return True if display is on."""
        payload = await self._send(CMD_POWER_GET)
        # 0x02 = on, 0x01 = standby
        return payload[0] == 0x02 if payload else False

    async def async_set_power(self, on: bool) -> None:
        """Power on (True) or standby (False)."""
        await self._send(CMD_POWER_SET, bytes([0x02 if on else 0x01]))

    async def async_get_input(self) -> Optional[int]:
        """Return current input source code, or None."""
        payload = await self._send(CMD_INPUT_GET)
        return payload[0] if payload else None

    async def async_set_input(self, code: int) -> None:
        """Select input by SICP code."""
        await self._send(CMD_INPUT_SET, bytes([code]))

    async def async_get_volume(self) -> Optional[int]:
        """Return current volume 0-100, or None."""
        payload = await self._send(CMD_VOLUME_GET)
        return payload[0] if payload else None

    async def async_set_volume(self, level: int) -> None:
        """Set absolute volume 0-100."""
        await self._send(CMD_VOLUME_SET, bytes([max(0, min(100, level))]))

    async def async_get_mute(self) -> bool:
        """Return True if muted."""
        payload = await self._send(CMD_MUTE_GET)
        return payload[0] == 0x01 if payload else False

    async def async_set_mute(self, muted: bool) -> None:
        """Mute or unmute."""
        await self._send(CMD_MUTE_SET, bytes([0x01 if muted else 0x00]))

    async def async_get_brightness(self) -> Optional[int]:
        """Return current brightness 0-100, or None."""
        payload = await self._send(CMD_BRIGHT_GET)
        return payload[0] if payload else None

    async def async_set_brightness(self, level: int) -> None:
        """Set brightness 0-100."""
        await self._send(CMD_BRIGHT_SET, bytes([max(0, min(100, level))]))

    async def async_get_contrast(self) -> Optional[int]:
        """Return current contrast 0-100, or None."""
        payload = await self._send(CMD_CONTRAST_GET)
        return payload[0] if payload else None

    async def async_set_contrast(self, level: int) -> None:
        """Set contrast 0-100."""
        await self._send(CMD_CONTRAST_SET, bytes([max(0, min(100, level))]))

    async def async_ping(self) -> bool:
        """Try a power-state get; return True if display responds."""
        try:
            await self.async_get_power()
            return True
        except SICPError:
            return False
