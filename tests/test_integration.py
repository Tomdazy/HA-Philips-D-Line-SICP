"""Tests de bout en bout : config entry, entités, commandes."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_dline_sicp.const import DOMAIN

from . import fake_monitor


async def _setup(hass: HomeAssistant, port: int) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": port, "monitor_id": 1, "group_id": 0,
              "include_group": True, "poll_interval": 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _entity_id(hass, platform, key):
    ent_reg = er.async_get(hass)
    return ent_reg.async_get_entity_id(platform, DOMAIN, f"philips_dline_127.0.0.1_1_{key}")


async def test_media_player_is_tv(hass: HomeAssistant, monitor):
    await _setup(hass, monitor)
    ent_reg = er.async_get(hass)
    tv = ent_reg.async_get_entity_id("media_player", DOMAIN, "philips_dline_127.0.0.1_1")
    state = hass.states.get(tv)
    assert state.state == "on"
    assert state.attributes["device_class"] == "tv"
    assert state.attributes["source"] == "HDMI 1"
    assert state.attributes["source_list"] == ["HDMI 1", "HDMI 2", "DisplayPort", "Media Player"]
    assert state.attributes["volume_level"] == 0.3

    device = dr.async_get(hass).async_get_device({(DOMAIN, "philips_dline_127.0.0.1_1")})
    assert device.model == "43BDL4550D/00"
    assert device.serial_number == "HA1A0917123456"

    await hass.services.async_call(
        "media_player", "select_source", {"entity_id": tv, "source": "DisplayPort"}, blocking=True
    )
    assert fake_monitor.STATE[0xAD][0] == 0x0A
    assert hass.states.get(tv).attributes["source"] == "DisplayPort"

    await hass.services.async_call(
        "media_player", "volume_set", {"entity_id": tv, "volume_level": 0.5}, blocking=True
    )
    assert fake_monitor.STATE[0x45] == bytes([50, 20])

    await hass.services.async_call("media_player", "turn_off", {"entity_id": tv}, blocking=True)
    assert fake_monitor.STATE[0x19] == b"\x01"
    assert hass.states.get(tv).state == "off"


async def test_settings_entities(hass: HomeAssistant, monitor):
    await _setup(hass, monitor)

    contrast = _entity_id(hass, "number", "contrast")
    assert hass.states.get(contrast).state == "45"
    await hass.services.async_call(
        "number", "set_value", {"entity_id": contrast, "value": 70}, blocking=True
    )
    # Seul le contraste change, les autres paramètres vidéo sont recopiés
    assert fake_monitor.STATE[0x33] == bytes([55, 50, 70, 5, 50, 50, 3])

    fmt = _entity_id(hass, "select", "picture_format")
    assert hass.states.get(fmt).state == "full"
    await hass.services.async_call(
        "select", "select_option", {"entity_id": fmt, "option": "wide_16_9"}, blocking=True
    )
    assert fake_monitor.STATE[0x3B] == b"\x06"

    freeze = _entity_id(hass, "switch", "freeze")
    await hass.services.async_call("switch", "turn_on", {"entity_id": freeze}, blocking=True)
    assert fake_monitor.STATE[0x76] == b"\x01"
    assert hass.states.get(freeze).state == "on"

    assert hass.states.get(_entity_id(hass, "sensor", "temperature")).state == "31"
    assert hass.states.get(_entity_id(hass, "sensor", "operating_hours")).state == "2445"
    assert hass.states.get(_entity_id(hass, "binary_sensor", "video_signal")).state == "on"

    light = _entity_id(hass, "light", "backlight")
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": light, "brightness": 255}, blocking=True
    )
    assert fake_monitor.STATE[0x33][0] == 100
    await hass.services.async_call("light", "turn_off", {"entity_id": light}, blocking=True)
    assert fake_monitor.STATE[0x71] == b"\x01"


async def test_unsupported_command_is_unavailable(hass: HomeAssistant, monitor):
    await _setup(hass, monitor)
    # 0x62 (ventilateur) n'existe pas sur le faux moniteur : NACK -> indisponible
    ent_reg = er.async_get(hass)
    fan = _entity_id(hass, "select", "fan_speed")
    ent_reg.async_update_entity(fan, disabled_by=None)
    await hass.config_entries.async_reload(hass.config_entries.async_entries(DOMAIN)[0].entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(fan).state == "unavailable"


async def test_raw_command_service(hass: HomeAssistant, monitor):
    await _setup(hass, monitor)
    result = await hass.services.async_call(
        DOMAIN, "send_raw_command", {"cmd": "0x19"}, blocking=True, return_response=True
    )
    assert result["results"][0]["payload"] == "02"
