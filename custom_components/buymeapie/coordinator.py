"""Data update coordinator for Buy Me a Pie."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    BuyMeAPieAuthError,
    BuyMeAPieClient,
    BuyMeAPieError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# {list_id: {"name": str, "items": [raw item dicts]}}
type BuyMeAPieData = dict[str, dict[str, Any]]


class BuyMeAPieCoordinator(DataUpdateCoordinator[BuyMeAPieData]):
    """Polls all lists and their items."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: BuyMeAPieClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> BuyMeAPieData:
        try:
            lists = await self.client.async_get_lists()
            items = await asyncio.gather(
                *(self.client.async_get_items(str(lst["id"])) for lst in lists)
            )
        except BuyMeAPieAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BuyMeAPieError as err:
            raise UpdateFailed(str(err)) from err

        return {
            str(lst["id"]): {"name": lst.get("name") or str(lst["id"]), "items": its}
            for lst, its in zip(lists, items, strict=True)
        }
