"""Philips SICP protocol client over TCP — connexion persistante."""
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

CONNECT_TIMEOUT  = 5.0
READ_TIMEOUT     = 2.0
# Délai minimum entre deux commandes — le moniteur ne peut pas
# traiter des requêtes en rafale sans respiration
INTER_CMD_DELAY  = 0.05   # 50 ms


class SICPError(Exception):
    """Base SICP error."""


class SICPConnectError(SICPError):
    """Cannot connect to display."""


class SICPTimeoutError(SICPError):
    """No reply in time."""


class SICPNACKError(SICPError):
    """Display replied NACK (checksum error)."""


class PhilipsSICP:
    """Async SICP client avec connexion persistante et lock de sérialisation.

    Le moniteur D-Line n'accepte qu'une commande à la fois sur la même
    connexion TCP. Ce client maintient une connexion ouverte et utilise
    un asyncio.Lock pour sérialiser les envois. En cas de déconnexion
    (ConnectionResetError, EOF), il reconnecte automatiquement.
    """

    def __init__(
        self,
        host: str,
        port: int = 5000,
        monitor_id: int = 1,
        group_id: int = 0,
        include_group: bool = True,
    ) -> None:
        self.host          = host
        self.port          = port
        self.monitor_id    = monitor_id
        self.group_id      = group_id
        self.include_group = include_group

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._lock   = asyncio.Lock()

    # ──────────────────────────────────────────
    # Connexion
    # ──────────────────────────────────────────

    async def _ensure_connected(self) -> None:
        """Ouvre la connexion si elle n'est pas déjà établie."""
        if self._writer is not None and not self._writer.is_closing():
            return
        _LOGGER.debug("SICP connexion vers %s:%d", self.host, self.port)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=CONNECT_TIMEOUT,
            )
            _LOGGER.debug("SICP connecté")
        except (OSError, TimeoutError, asyncio.TimeoutError) as exc:
            self._reader = self._writer = None
            raise SICPConnectError(
                f"Impossible de joindre {self.host}:{self.port} : {exc}"
            ) from exc

    def _disconnect(self) -> None:
        """Ferme la connexion proprement (best-effort)."""
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass
        self._reader = self._writer = None

    async def disconnect(self) -> None:
        """Ferme proprement la connexion (appelé au unload)."""
        async with self._lock:
            self._disconnect()

    # ──────────────────────────────────────────
    # Framing
    # ──────────────────────────────────────────

    def _build_packet(self, command: int, data: bytes = b"") -> bytes:
        """Construit un paquet SICP v2.

        Format: [len] [monitor_id] [group_id?] [cmd] [data...] [checksum XOR]
        len = longueur totale du paquet (inclut len et checksum).
        """
        if self.include_group:
            header = bytes([self.monitor_id, self.group_id, command])
        else:
            header = bytes([self.monitor_id, command])

        body   = header + data
        length = len(body) + 2          # +1 pour len, +1 pour checksum
        packet = bytes([length]) + body
        chk    = 0
        for b in packet:
            chk ^= b
        return packet + bytes([chk])

    def _parse_reply(self, raw: bytes) -> bytes:
        """Extrait le payload d'une réponse SICP.

        Trame de réponse (avec group):
          [0]      len
          [1]      monitor_id
          [2]      group_id
          [3]      cmd_echo
          [4..n-2] payload
          [n-1]    checksum XOR

        Trame sans group:
          [0]      len
          [1]      monitor_id
          [2]      cmd_echo
          [3..n-2] payload
          [n-1]    checksum XOR
        """
        _LOGGER.debug("SICP <- raw (%d B): %s", len(raw), raw.hex())

        if len(raw) < 4:
            raise SICPError(f"Réponse trop courte ({len(raw)} octets) : {raw.hex()}")

        # Vérification checksum
        chk = 0
        for b in raw[:-1]:
            chk ^= b
        if chk != raw[-1]:
            _LOGGER.warning(
                "SICP checksum attendu 0x%02x reçu 0x%02x — raw: %s",
                chk, raw[-1], raw.hex(),
            )

        if self.include_group:
            payload = raw[4:-1]
        else:
            payload = raw[3:-1]

        _LOGGER.debug("SICP payload: %s", payload.hex() if payload else "(vide)")
        return payload

    # ──────────────────────────────────────────
    # Envoi / réception
    # ──────────────────────────────────────────

    async def _send(self, command: int, data: bytes = b"") -> bytes:
        """Envoie une commande et retourne le payload de la réponse.

        Utilise la connexion persistante avec reconnexion automatique.
        Le lock garantit qu'une seule commande circule à la fois.
        """
        async with self._lock:
            packet = self._build_packet(command, data)
            _LOGGER.debug("SICP -> 0x%02x  pkt: %s", command, packet.hex())

            # Connexion (ou reconnexion si nécessaire)
            await self._ensure_connected()

            try:
                self._writer.write(packet)
                await self._writer.drain()

                # Petit délai pour laisser le moniteur traiter la commande
                await asyncio.sleep(INTER_CMD_DELAY)

                try:
                    reply = await asyncio.wait_for(
                        self._reader.read(64), timeout=READ_TIMEOUT
                    )
                except (TimeoutError, asyncio.TimeoutError, asyncio.CancelledError) as exc:
                    self._disconnect()
                    raise SICPTimeoutError(
                        f"Pas de réponse de {self.host} (cmd=0x{command:02x})"
                    ) from exc

                if not reply:
                    # EOF = le moniteur a fermé la connexion
                    self._disconnect()
                    raise SICPTimeoutError(
                        f"Connexion fermée par le moniteur (cmd=0x{command:02x})"
                    )

                return self._parse_reply(reply)

            except (ConnectionResetError, ConnectionAbortedError,
                    BrokenPipeError, OSError) as exc:
                self._disconnect()
                raise SICPConnectError(
                    f"Connexion réinitialisée par le moniteur (cmd=0x{command:02x}): {exc}"
                ) from exc

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    async def async_get_power(self) -> bool:
        """Retourne True si l'écran est allumé."""
        payload = await self._send(CMD_POWER_GET)
        return payload[0] == 0x02 if payload else False

    async def async_set_power(self, on: bool) -> None:
        """Allume (True) ou met en veille (False)."""
        await self._send(CMD_POWER_SET, bytes([0x02 if on else 0x01]))

    async def async_get_input(self) -> Optional[int]:
        """Retourne le code SICP de l'entrée active, ou None."""
        payload = await self._send(CMD_INPUT_GET)
        return payload[0] if payload else None

    async def async_set_input(self, code: int) -> None:
        """Sélectionne une entrée par son code SICP."""
        await self._send(CMD_INPUT_SET, bytes([code]))

    async def async_get_volume(self) -> Optional[int]:
        """Retourne le volume courant (0-100), ou None."""
        payload = await self._send(CMD_VOLUME_GET)
        return payload[0] if payload else None

    async def async_set_volume(self, level: int) -> None:
        """Règle le volume (0-100)."""
        await self._send(CMD_VOLUME_SET, bytes([max(0, min(100, level))]))

    async def async_get_mute(self) -> bool:
        """Retourne True si le son est coupé."""
        payload = await self._send(CMD_MUTE_GET)
        return payload[0] == 0x01 if payload else False

    async def async_set_mute(self, muted: bool) -> None:
        """Active ou désactive le mute."""
        await self._send(CMD_MUTE_SET, bytes([0x01 if muted else 0x00]))

    async def async_get_brightness(self) -> Optional[int]:
        """Retourne la luminosité (0-100), ou None."""
        payload = await self._send(CMD_BRIGHT_GET)
        return payload[0] if payload else None

    async def async_set_brightness(self, level: int) -> None:
        """Règle la luminosité (0-100)."""
        await self._send(CMD_BRIGHT_SET, bytes([max(0, min(100, level))]))

    async def async_get_contrast(self) -> Optional[int]:
        """Retourne le contraste (0-100), ou None."""
        payload = await self._send(CMD_CONTRAST_GET)
        return payload[0] if payload else None

    async def async_set_contrast(self, level: int) -> None:
        """Règle le contraste (0-100)."""
        await self._send(CMD_CONTRAST_SET, bytes([max(0, min(100, level))]))

    async def async_ping(self) -> bool:
        """Tente un get power ; retourne True si le moniteur répond."""
        try:
            await self.async_get_power()
            return True
        except (SICPError, TimeoutError, asyncio.TimeoutError,
                asyncio.CancelledError, OSError):
            return False
