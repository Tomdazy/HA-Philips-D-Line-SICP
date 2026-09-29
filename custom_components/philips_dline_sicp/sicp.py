"""Client asynchrone du protocole Philips SICP (v2.09) sur TCP.

Format d'une trame :  [MsgSize] [Control] [Group] [Data0..DataN] [Checksum]
  - MsgSize  : longueur totale de la trame (MsgSize et Checksum inclus)
  - Control  : Monitor ID (1-255)
  - Group    : Group ID (0 = pilotage par Monitor ID)
  - Data0    : code de commande
  - Checksum : XOR de tous les octets précédents

Réponses :
  - Get : trame de rapport, Data0 = code de la commande demandée
  - Set : rapport générique Data0 = 0x00, Data1 = 0x06 (ACK) / 0x15 (NACK) / 0x18 (NAV)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

_LOGGER = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Codes de commande SICP
# ──────────────────────────────────────────────
CMD_COMM_CONTROL    = 0x00
CMD_POWER_SET       = 0x18
CMD_POWER_GET       = 0x19
CMD_INPUT_SET       = 0xAC
CMD_INPUT_GET       = 0xAD
CMD_SOURCES_GET     = 0xAB
CMD_VOLUME_SET      = 0x44
CMD_VOLUME_GET      = 0x45
CMD_MUTE_GET        = 0x46
CMD_MUTE_SET        = 0x47
CMD_VIDEO_SET       = 0x32
CMD_VIDEO_GET       = 0x33
CMD_MODEL_GET       = 0xA1
CMD_PLATFORM_GET    = 0xA2
CMD_SERIAL_GET      = 0x15

ACK  = 0x06
NACK = 0x15
NAV  = 0x18

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT    = 2.0
# La doc impose d'attendre la réponse avant la commande suivante ; on garde
# une petite respiration supplémentaire, certains firmwares saturent sinon.
INTER_CMD_DELAY = 0.05


class SICPError(Exception):
    """Erreur SICP générique."""


class SICPConnectError(SICPError):
    """Impossible de joindre le moniteur."""


class SICPTimeoutError(SICPError):
    """Pas de réponse dans le délai imparti."""


class SICPNACKError(SICPError):
    """Le moniteur a répondu NACK (trame corrompue ou commande inconnue)."""


class SICPNAVError(SICPError):
    """Le moniteur a répondu NAV (commande non disponible ou impossible en l'état)."""


class PhilipsSICP:
    """Client SICP avec connexion persistante et envois sérialisés.

    Le moniteur ne traite qu'une commande à la fois : un asyncio.Lock
    sérialise les échanges, et la connexion est rouverte automatiquement
    si le moniteur la ferme.
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
        self._lock = asyncio.Lock()

    # ──────────────────────────────────────────
    # Connexion
    # ──────────────────────────────────────────

    async def _ensure_connected(self) -> None:
        if self._writer is not None and not self._writer.is_closing():
            return
        _LOGGER.debug("SICP connexion vers %s:%d", self.host, self.port)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=CONNECT_TIMEOUT,
            )
        except (OSError, TimeoutError, asyncio.TimeoutError) as exc:
            self._reader = self._writer = None
            raise SICPConnectError(
                f"Impossible de joindre {self.host}:{self.port} : {exc}"
            ) from exc

    def _disconnect(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:  # pylint: disable=broad-except
                pass
        self._reader = self._writer = None

    async def disconnect(self) -> None:
        """Ferme la connexion (appelé au déchargement)."""
        async with self._lock:
            self._disconnect()

    # ──────────────────────────────────────────
    # Framing
    # ──────────────────────────────────────────

    def build_packet(self, command: int, data: bytes = b"") -> bytes:
        """Construit une trame SICP complète, checksum compris."""
        if self.include_group:
            body = bytes([self.monitor_id, self.group_id, command]) + data
        else:
            body = bytes([self.monitor_id, command]) + data
        packet = bytes([len(body) + 2]) + body
        chk = 0
        for b in packet:
            chk ^= b
        return packet + bytes([chk])

    async def _read_frame(self, timeout: float) -> bytes:
        """Lit exactement une trame en s'appuyant sur l'octet MsgSize."""
        assert self._reader is not None
        size = await asyncio.wait_for(self._reader.readexactly(1), timeout=timeout)
        length = size[0]
        if length < 4 or length > 0x28:
            raise SICPError(f"Octet MsgSize invalide : 0x{length:02x}")
        rest = await asyncio.wait_for(self._reader.readexactly(length - 1), timeout=timeout)
        frame = size + rest

        chk = 0
        for b in frame[:-1]:
            chk ^= b
        if chk != frame[-1]:
            _LOGGER.debug(
                "SICP checksum attendu 0x%02x reçu 0x%02x : %s", chk, frame[-1], frame.hex()
            )
        return frame

    def _split_reply(self, frame: bytes) -> tuple[int, bytes]:
        """Retourne (code écho, payload) d'une trame de réponse."""
        offset = 3 if self.include_group else 2
        if len(frame) < offset + 2:
            raise SICPError(f"Réponse trop courte : {frame.hex()}")
        return frame[offset], frame[offset + 1:-1]

    # ──────────────────────────────────────────
    # Échange
    # ──────────────────────────────────────────

    async def _exchange(self, command: int, data: bytes, timeout: float) -> tuple[int, bytes]:
        """Envoie une trame et retourne la réponse qui lui correspond."""
        packet = self.build_packet(command, data)
        await self._ensure_connected()
        assert self._writer is not None
        _LOGGER.debug("SICP -> %s", packet.hex())
        self._writer.write(packet)
        await self._writer.drain()

        # Une réponse tardive à une commande précédente peut traîner dans le
        # tampon : on l'ignore et on lit la suivante (au plus deux fois).
        for _ in range(3):
            frame = await self._read_frame(timeout)
            _LOGGER.debug("SICP <- %s", frame.hex())
            echo, payload = self._split_reply(frame)
            if echo in (command, CMD_COMM_CONTROL):
                return echo, payload
            _LOGGER.debug("SICP trame ignorée (écho 0x%02x ≠ 0x%02x)", echo, command)
        raise SICPError(f"Aucune réponse cohérente pour la commande 0x{command:02x}")

    async def send(
        self, command: int, data: bytes = b"", timeout: float = READ_TIMEOUT
    ) -> tuple[int, bytes]:
        """Envoie une commande brute ; retourne (code écho, payload).

        Réessaie une fois sur une connexion neuve si la connexion
        persistante a été fermée par le moniteur.
        """
        async with self._lock:
            for attempt in (1, 2):
                try:
                    result = await self._exchange(command, data, timeout)
                    await asyncio.sleep(INTER_CMD_DELAY)
                    return result
                except (asyncio.IncompleteReadError, ConnectionResetError,
                        ConnectionAbortedError, BrokenPipeError) as exc:
                    self._disconnect()
                    if attempt == 2:
                        raise SICPConnectError(
                            f"Connexion fermée par le moniteur (cmd=0x{command:02x}) : {exc}"
                        ) from exc
                except (TimeoutError, asyncio.TimeoutError) as exc:
                    self._disconnect()
                    raise SICPTimeoutError(
                        f"Pas de réponse de {self.host} (cmd=0x{command:02x})"
                    ) from exc
                except SICPConnectError:
                    raise
                except SICPError:
                    self._disconnect()
                    raise
                except OSError as exc:
                    self._disconnect()
                    raise SICPConnectError(
                        f"Erreur réseau (cmd=0x{command:02x}) : {exc}"
                    ) from exc
        raise SICPError("unreachable")

    @staticmethod
    def _raise_for_status(command: int, echo: int, payload: bytes) -> None:
        if echo != CMD_COMM_CONTROL or not payload:
            return
        status = payload[0]
        if status == NACK:
            raise SICPNACKError(f"NACK pour la commande 0x{command:02x}")
        if status == NAV:
            raise SICPNAVError(f"NAV pour la commande 0x{command:02x}")

    async def async_get(
        self, command: int, data: bytes = b"", timeout: float = READ_TIMEOUT
    ) -> bytes:
        """Commande Get : retourne les octets DATA[1..N] du rapport."""
        echo, payload = await self.send(command, data, timeout)
        self._raise_for_status(command, echo, payload)
        if echo == CMD_COMM_CONTROL:
            # ACK générique à la place d'un rapport : aucune donnée exploitable
            raise SICPNAVError(f"Pas de rapport pour la commande 0x{command:02x}")
        return payload

    async def async_set(self, command: int, data: bytes = b"") -> None:
        """Commande Set : lève une exception si le moniteur ne répond pas ACK."""
        echo, payload = await self.send(command, data)
        self._raise_for_status(command, echo, payload)

    # ──────────────────────────────────────────
    # Raccourcis
    # ──────────────────────────────────────────

    async def async_get_power(self) -> bool:
        payload = await self.async_get(CMD_POWER_GET)
        return bool(payload) and payload[0] == 0x02

    async def async_set_power(self, on: bool) -> None:
        await self.async_set(CMD_POWER_SET, bytes([0x02 if on else 0x01]))

    async def async_set_input(self, code: int, playlist: int | None = None) -> None:
        """Sélectionne une source (DATA[2] = playlist/URL, DATA[3] = libellé OSD)."""
        # Les exemples de la doc utilisent 0x09 quand aucune playlist n'est visée
        tag = 0x09 if playlist is None else playlist
        await self.async_set(CMD_INPUT_SET, bytes([code, tag, 0x01, 0x00]))

    async def async_set_volume(self, speaker: int | None, audio_out: int | None = None) -> None:
        """Règle le volume ; 0xFF laisse une sortie inchangée."""
        spk = 0xFF if speaker is None else max(0, min(100, speaker))
        out = 0xFF if audio_out is None else max(0, min(100, audio_out))
        try:
            await self.async_set(CMD_VOLUME_SET, bytes([spk, out]))
        except (SICPNACKError, SICPNAVError):
            # Plateformes Eagle / Himalaya 1.x : un seul octet (haut-parleurs)
            if speaker is None:
                raise
            await self.async_set(CMD_VOLUME_SET, bytes([spk]))

    async def async_get_text(self, command: int, data: bytes = b"") -> str | None:
        """Get dont la réponse est une chaîne ASCII (modèle, version, série…)."""
        payload = await self.async_get(command, data)
        text = payload.decode("ascii", errors="ignore").strip("\x00 ").strip()
        return text or None

    async def async_get_sources(self) -> list[int]:
        """Liste des codes de sources disponibles (commande 0xAB, SICP ≥ 2.05)."""
        payload = await self.async_get(CMD_SOURCES_GET)
        if not payload:
            return []
        count = payload[0]
        return list(payload[1:1 + count])

    async def async_ping(self) -> bool:
        """Retourne True si le moniteur répond à un Get power."""
        try:
            await self.async_get_power()
            return True
        except SICPError:
            return False
