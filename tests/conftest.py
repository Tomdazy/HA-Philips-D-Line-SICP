"""Fixtures de test : un faux moniteur SICP sur un port TCP local."""
from __future__ import annotations

import copy

import pytest

from . import fake_monitor

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def monitor(socket_enabled):
    """Démarre le faux moniteur et restaure son état après le test."""
    saved = copy.deepcopy(fake_monitor.STATE)
    fake_monitor.LOG.clear()
    server, port = await fake_monitor.start()
    yield port
    await fake_monitor.stop(server)
    fake_monitor.STATE.clear()
    fake_monitor.STATE.update(saved)
