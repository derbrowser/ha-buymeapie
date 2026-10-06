"""Data update coordinator for Buy Me a Pie."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    BuyMeAPieAuthError,
    BuyMeAPieClient,
    BuyMeAPieError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, GHOST_STORAGE_VERSION

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
        # Ghost items: still returned by the API, but gone server-side (404 on
        # PUT/DELETE). They are hidden so they cannot break the todo list.
        self._ghost_store: Store[dict[str, list[str]]] = Store(
            hass, GHOST_STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.ghosts"
        )
        self._ghosts: dict[str, set[str]] = {}
        self._ghosts_loaded = False

    async def _async_load_ghosts(self) -> None:
        if self._ghosts_loaded:
            return
        stored = await self._ghost_store.async_load() or {}
        self._ghosts = {list_id: set(ids) for list_id, ids in stored.items()}
        self._ghosts_loaded = True

    async def _async_save_ghosts(self) -> None:
        await self._ghost_store.async_save(
            {list_id: sorted(ids) for list_id, ids in self._ghosts.items() if ids}
        )

    async def async_mark_ghost(self, list_id: str, item_id: str) -> None:
        """Remember an item that the API lists but cannot be changed (404)."""
        await self._async_load_ghosts()
        raw = next(
            (
                item
                for item in (self.data or {}).get(list_id, {}).get("items", [])
                if str(item.get("id")) == item_id
            ),
            None,
        )
        _LOGGER.warning(
            "Item %s in list %s no longer exists on the server (404); hiding it. "
            "Raw API record: %s",
            item_id,
            list_id,
            json.dumps(raw, ensure_ascii=False, default=str),
        )
        self._ghosts.setdefault(list_id, set()).add(item_id)
        await self._async_save_ghosts()

    async def _async_update_data(self) -> BuyMeAPieData:
        await self._async_load_ghosts()
        try:
            lists = await self.client.async_get_lists()
            items = await asyncio.gather(
                *(self.client.async_get_items(str(lst["id"])) for lst in lists)
            )
        except BuyMeAPieAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BuyMeAPieError as err:
            raise UpdateFailed(str(err)) from err

        data: BuyMeAPieData = {}
        changed = False
        for lst, its in zip(lists, items, strict=True):
            list_id = str(lst["id"])
            ghosts = self._ghosts.get(list_id, set())
            present = {str(item["id"]) for item in its}
            # Forget ghosts the API no longer returns, so the set stays small.
            stale = ghosts - present
            if stale:
                ghosts -= stale
                changed = True
            data[list_id] = {
                "name": lst.get("name") or list_id,
                "items": [item for item in its if str(item["id"]) not in ghosts],
            }
        if changed:
            await self._async_save_ghosts()
        return data
