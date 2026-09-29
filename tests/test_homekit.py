"""Vérifie que HomeKit Bridge expose le moniteur comme un téléviseur."""
import itertools
from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.philips_dline_sicp.const import DOMAIN

from .test_integration import _setup

pytest.importorskip("pyhap", reason="HAP-python requis (composant homekit)")


async def test_exposed_as_homekit_television(hass: HomeAssistant, monitor):
    from pyhap.loader import get_loader

    from homeassistant.components.homekit.accessories import TYPES, get_accessory

    await _setup(hass, monitor)
    tv = er.async_get(hass).async_get_entity_id(
        "media_player", DOMAIN, "philips_dline_127.0.0.1_1"
    )
    state = hass.states.get(tv)

    driver = MagicMock()
    driver.loader = get_loader()
    iids = itertools.count(1)
    driver.iid_storage.get_or_allocate_iid.side_effect = lambda *args: next(iids)
    acc = get_accessory(hass, driver, state, 2, {})
    assert isinstance(acc, TYPES["TelevisionMediaPlayer"])

    services = {s.display_name for s in acc.services}
    assert "Television" in services
    assert "TelevisionSpeaker" in services  # volume et sourdine depuis la télécommande iOS
    inputs = [s for s in acc.services if s.display_name == "InputSource"]
    assert len(inputs) == len(state.attributes["source_list"])
