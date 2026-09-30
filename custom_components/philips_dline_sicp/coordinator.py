"""Coordinateur de polling du moniteur Philips D-Line."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .wol import send_magic_packet
from .sicp import (
    CMD_MODEL_GET,
    CMD_PLATFORM_GET,
    CMD_POWER_GET,
    CMD_SERIAL_GET,
    PhilipsSICP,
    SICPError,
    SICPNACKError,
    SICPNAVError,
    SICPTimeoutError,
)

_LOGGER = logging.getLogger(__name__)

# Une requête Get = (code commande, octets de données)
Query = tuple[int, bytes]

TIER_FAST   = "fast"     # à chaque cycle, écran allumé
TIER_SLOW   = "slow"     # toutes les slow_poll_interval secondes
TIER_STATIC = "static"   # une seule fois (modèle, versions…)

# Une commande non supportée est mise de côté pendant ce délai
UNSUPPORTED_BACKOFF = 3600
MAX_NAV_FAILURES     = 3
MAX_TIMEOUT_FAILURES = 2
# Juste après l'allumage, le moniteur répond NAV à presque tout
WARMUP_SECONDS = 60

# Requêtes d'identification lues au démarrage (DeviceInfo)
Q_MODEL        = (CMD_MODEL_GET, b"\x00")
Q_FIRMWARE     = (CMD_MODEL_GET, b"\x01")
Q_BUILD_DATE   = (CMD_MODEL_GET, b"\x02")
Q_ANDROID_FW   = (CMD_MODEL_GET, b"\x03")
Q_SICP_VERSION = (CMD_PLATFORM_GET, b"\x00")
Q_PLATFORM     = (CMD_PLATFORM_GET, b"\x01")
Q_PLATFORM_VER = (CMD_PLATFORM_GET, b"\x02")
Q_SERIAL       = (CMD_SERIAL_GET, b"")
IDENTITY_QUERIES = [
    Q_MODEL, Q_FIRMWARE, Q_BUILD_DATE, Q_ANDROID_FW,
    Q_SICP_VERSION, Q_PLATFORM, Q_PLATFORM_VER, Q_SERIAL,
]


def query_label(query: Query) -> str:
    cmd, data = query
    return f"0x{cmd:02X}" + (f":{data.hex()}" if data else "")


class PhilipsDLineCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Interroge le moniteur ; chaque Get n'est envoyé qu'une fois par cycle,
    même s'il alimente plusieurs entités (ex. 0x33 → luminosité, contraste…)."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PhilipsSICP,
        poll_interval: int,
        slow_poll_interval: int,
        mac: str | None = None,
        cache: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval) if poll_interval > 0 else None,
        )
        self.client = client
        self.slow_poll_interval = max(slow_poll_interval, poll_interval)
        self.mac = mac

        self.power: bool | None = None
        # False tant que le moniteur ne répond pas au Get power (veille profonde…)
        self.reachable = False
        self.payloads: dict[Query, bytes] = {}
        self.sources: list[int] = []
        self._load_cache(cache or {})

        self._tiers: dict[Query, str] = {}
        self._refcount: dict[Query, int] = {}
        self._pending: set[Query] = set()
        self._last_slow = 0.0
        self._failures: dict[Query, int] = {}
        self._skip_until: dict[Query, float] = {}
        self._on_since = 0.0

    # ──────────────────────────────────────────
    # Abonnements des entités
    # ──────────────────────────────────────────

    @callback
    def register(self, query: Query, tier: str) -> Callable[[], None]:
        """Déclare qu'une entité a besoin de cette requête ; retourne le désabonnement."""
        self._refcount[query] = self._refcount.get(query, 0) + 1
        # Le rythme le plus rapide demandé l'emporte
        order = (TIER_FAST, TIER_SLOW, TIER_STATIC)
        current = self._tiers.get(query)
        if current is None or order.index(tier) < order.index(current):
            self._tiers[query] = tier
        if query not in self.payloads:
            self._pending.add(query)

        @callback
        def _unregister() -> None:
            self._refcount[query] -= 1
            if self._refcount[query] <= 0:
                self._refcount.pop(query, None)
                self._tiers.pop(query, None)
                self._pending.discard(query)

        return _unregister

    def payload(self, query: Query) -> bytes | None:
        return self.payloads.get(query)

    def is_supported(self, query: Query) -> bool:
        return self._skip_until.get(query, 0) <= time.monotonic()

    # ──────────────────────────────────────────
    # Cache d'identité (persisté dans l'entrée de configuration)
    # ──────────────────────────────────────────

    def _load_cache(self, cache: dict[str, Any]) -> None:
        """Recharge modèle, versions et sources lus lors d'un démarrage précédent.

        Un moniteur en veille ne répond souvent plus en SICP : sans ce cache,
        la fiche appareil et surtout la liste des entrées exposée à HomeKit
        changeraient à chaque redémarrage de Home Assistant.
        """
        identity = cache.get("identity", {})
        for query in IDENTITY_QUERIES:
            value = identity.get(query_label(query))
            if value:
                self.payloads[query] = bytes.fromhex(value)
        self.sources = [int(c) for c in cache.get("sources", [])]

    def cache_snapshot(self) -> dict[str, Any]:
        """État à persister : identité et sources connues."""
        return {
            "identity": {
                query_label(q): self.payloads[q].hex()
                for q in IDENTITY_QUERIES
                if q in self.payloads
            },
            "sources": list(self.sources),
        }

    # ──────────────────────────────────────────
    # Polling
    # ──────────────────────────────────────────

    async def async_fetch_identity(self) -> None:
        """Lit modèle, versions, numéro de série et sources, si le moniteur répond."""
        try:
            self.power = await self.client.async_get_power()
            self.reachable = True
        except SICPError as exc:
            _LOGGER.info(
                "Le moniteur %s ne répond pas (veille ?) : identité reprise du cache (%s)",
                self.client.host, exc,
            )
            return
        for query in IDENTITY_QUERIES:
            await self._fetch(query)
        try:
            self.sources = await self.client.async_get_sources() or self.sources
        except SICPError as exc:
            _LOGGER.debug("Liste des sources (0xAB) indisponible : %s", exc)

    async def _fetch(self, query: Query) -> None:
        if not self.is_supported(query):
            return
        cmd, data = query
        try:
            self.payloads[query] = await self.client.async_get(cmd, data)
            self._failures.pop(query, None)
            self._pending.discard(query)
        except SICPNACKError:
            self._mark_failure(query, permanent=True)
        except SICPNAVError:
            if time.monotonic() - self._on_since >= WARMUP_SECONDS:
                self._mark_failure(query, limit=MAX_NAV_FAILURES)
        except SICPTimeoutError:
            self._mark_failure(query, limit=MAX_TIMEOUT_FAILURES)

    def _mark_failure(self, query: Query, permanent: bool = False, limit: int = 1) -> None:
        count = self._failures.get(query, 0) + 1
        self._failures[query] = count
        if permanent or count >= limit:
            _LOGGER.debug(
                "Commande %s non supportée par ce moniteur, mise en pause %d s",
                query_label(query), UNSUPPORTED_BACKOFF,
            )
            self._skip_until[query] = time.monotonic() + UNSUPPORTED_BACKOFF
            self._failures.pop(query, None)
            self._pending.discard(query)
            self.payloads.pop(query, None)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            power = await self.client.async_get_power()
        except SICPError as exc:
            self.reachable = False
            raise UpdateFailed(f"Le moniteur ne répond pas : {exc}") from exc

        was_on = self.power if self.reachable else None
        self.reachable = True
        self.power = power
        if power and was_on is False:
            self._on_since = time.monotonic()

        # En veille, la plupart des commandes répondent NAV : on n'insiste pas.
        if power:
            now = time.monotonic()
            slow_due = (
                was_on is not True
                or now - self._last_slow >= self.slow_poll_interval
            )
            for query, tier in list(self._tiers.items()):
                if query[0] == CMD_POWER_GET:
                    continue
                if (
                    query in self._pending
                    or tier == TIER_FAST
                    or (tier == TIER_SLOW and slow_due)
                ):
                    await self._fetch(query)
            if slow_due:
                self._last_slow = now

        return {"power": power, "payloads": dict(self.payloads)}

    # ──────────────────────────────────────────
    # Commandes
    # ──────────────────────────────────────────

    async def async_refresh_queries(self, queries: list[Query]) -> None:
        """Relit quelques requêtes et publie l'état sans attendre le cycle."""
        for query in queries:
            self._skip_until.pop(query, None)
            await self._fetch(query)
        self.async_set_updated_data({"power": self.power, "payloads": dict(self.payloads)})

    async def async_command(
        self,
        cmd: int,
        data: bytes = b"",
        refresh: list[Query] | None = None,
    ) -> None:
        """Envoie une commande Set et relit les requêtes concernées."""
        try:
            await self.client.async_set(cmd, data)
        except SICPError as exc:
            raise HomeAssistantError(
                f"Commande SICP 0x{cmd:02X} refusée par le moniteur : {exc}"
            ) from exc
        if refresh:
            await self.async_refresh_queries(refresh)

    async def async_set_power(self, on: bool) -> None:
        try:
            await self.client.async_set_power(on)
        except SICPError as exc:
            # En veille profonde, le service SICP ne répond plus : seul le
            # Wake on LAN (option WOL du moniteur) peut encore le réveiller.
            if not on or not self.mac:
                hint = "" if on is False else " ; renseignez l'adresse MAC pour le Wake on LAN"
                raise HomeAssistantError(f"Changement d'alimentation refusé : {exc}{hint}") from exc
            _LOGGER.info("SICP muet (%s) : allumage de %s par Wake on LAN", exc, self.client.host)
            await self.hass.async_add_executor_job(
                send_magic_packet, self.mac, self.client.host
            )
        if on and self.power is False:
            self._on_since = time.monotonic()
        self.power = on
        self.async_set_updated_data({"power": on, "payloads": dict(self.payloads)})
        # L'écran met quelques secondes à accepter les autres commandes
        await self.async_request_refresh()
