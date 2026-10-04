"""Todo platform: one todo list entity per Buy Me a Pie list."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BuyMeAPieError
from .const import DOMAIN
from .coordinator import BuyMeAPieCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import BuyMeAPieConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BuyMeAPieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create entities for all lists, and for lists added later."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    def _add_new_lists() -> None:
        new = [list_id for list_id in coordinator.data if list_id not in known]
        if new:
            known.update(new)
            async_add_entities(
                BuyMeAPieTodoListEntity(coordinator, entry.entry_id, list_id)
                for list_id in new
            )

    _add_new_lists()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_lists))


class BuyMeAPieTodoListEntity(CoordinatorEntity[BuyMeAPieCoordinator], TodoListEntity):
    """A Buy Me a Pie shopping list."""

    _attr_has_entity_name = False
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self, coordinator: BuyMeAPieCoordinator, entry_id: str, list_id: str
    ) -> None:
        super().__init__(coordinator)
        self._list_id = list_id
        self._attr_unique_id = f"{entry_id}_{list_id}"

    @property
    def _list(self) -> dict[str, Any] | None:
        return self.coordinator.data.get(self._list_id)

    @property
    def available(self) -> bool:
        return super().available and self._list is not None

    @property
    def name(self) -> str:
        lst = self._list
        return lst["name"] if lst else f"{DOMAIN} {self._list_id}"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        lst = self._list
        if lst is None:
            return None
        items = [
            TodoItem(
                uid=str(raw["id"]),
                summary=raw.get("title") or "",
                status=(
                    TodoItemStatus.COMPLETED
                    if raw.get("is_purchased")
                    else TodoItemStatus.NEEDS_ACTION
                ),
                description=raw.get("amount") or None,
            )
            for raw in lst["items"]
        ]
        # Open items first, purchased ones at the bottom (stable otherwise).
        items.sort(key=lambda item: item.status == TodoItemStatus.COMPLETED)
        return items

    def _existing(self, uid: str) -> dict[str, Any] | None:
        lst = self._list
        if lst is None:
            return None
        return next((raw for raw in lst["items"] if str(raw["id"]) == uid), None)

    async def _call(self, *coros: Any) -> None:
        """Run API calls, map errors, then refresh."""
        try:
            await asyncio.gather(*coros)
        except BuyMeAPieError as err:
            raise HomeAssistantError(f"Buy Me a Pie: {err}") from err
        finally:
            await self.coordinator.async_request_refresh()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        await self._call(
            self.coordinator.client.async_add_item(
                self._list_id, item.summary or "", item.description or ""
            )
        )

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.uid is None:
            raise HomeAssistantError("Item has no id")
        existing = self._existing(item.uid)
        title = item.summary or (existing or {}).get("title") or ""
        await self._call(
            self.coordinator.client.async_update_item(
                self._list_id,
                item.uid,
                title=title,
                amount=item.description or "",
                is_purchased=item.status == TodoItemStatus.COMPLETED,
            )
        )

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        await self._call(
            *(
                self.coordinator.client.async_delete_item(self._list_id, uid)
                for uid in uids
            )
        )
