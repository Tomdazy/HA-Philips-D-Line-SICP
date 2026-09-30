"""Wake on LAN : allumage d'un moniteur dont le service SICP dort en veille."""
from __future__ import annotations

import logging
import re
import socket

_LOGGER = logging.getLogger(__name__)

_MAC_RE = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


def normalize_mac(mac: str | None) -> str | None:
    """Retourne l'adresse au format aa:bb:cc:dd:ee:ff, ou None si invalide."""
    if not mac:
        return None
    mac = mac.strip().lower().replace("-", ":")
    return mac if _MAC_RE.match(mac) and mac != "00:00:00:00:00:00" else None


def lookup_mac(host: str) -> str | None:
    """Cherche l'adresse MAC de `host` dans la table ARP du système (Linux).

    La table n'est renseignée qu'après un échange récent avec l'hôte : à
    appeler juste après une connexion TCP au moniteur.
    """
    try:
        with open("/proc/net/arp", encoding="ascii") as arp:
            next(arp, None)  # en-tête
            for line in arp:
                fields = line.split()
                if len(fields) >= 4 and fields[0] == host:
                    return normalize_mac(fields[3])
    except OSError:
        pass
    return None


def send_magic_packet(mac: str, host: str | None = None) -> None:
    """Envoie le paquet magique en broadcast, et en direct vers l'hôte."""
    packet = b"\xff" * 6 + bytes.fromhex(mac.replace(":", "")) * 16
    targets = [("255.255.255.255", 9)]
    if host:
        targets.append((host, 9))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for target in targets:
            try:
                sock.sendto(packet, target)
            except OSError as exc:
                _LOGGER.debug("Wake on LAN vers %s impossible : %s", target, exc)
    _LOGGER.debug("Wake on LAN envoyé à %s", mac)
