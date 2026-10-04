"""The Buy Me a Pie integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import BuyMeAPieClient
from .const import CONF_PIN
from .coordinator import BuyMeAPieCoordinator

PLATFORMS: list[Platform] = [Platform.TODO]

type BuyMeAPieConfigEntry = ConfigEntry[BuyMeAPieCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BuyMeAPieConfigEntry) -> bool:
    """Set up Buy Me a Pie from a config entry."""
    # Own session: the server hands out a session cookie that must not be
    # shared with other integrations.
    client = BuyMeAPieClient(
        async_create_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PIN],
    )
    coordinator = BuyMeAPieCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BuyMeAPieConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
