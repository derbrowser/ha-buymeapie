"""Async client for the (unofficial) Buy Me a Pie web API.

Endpoints, as used by the web app at https://app.buymeapie.com:

    GET    bauth                         login check (HTTP Basic: e-mail + PIN)
    GET    lists                         all lists
    POST   lists                         create list
    PUT    lists/{id}                    rename list
    DELETE lists/{id}                    delete list
    GET    lists/{id}/items              items of a list
    POST   lists/{id}/items              add item
    PUT    lists/{id}/items/{item_id}    update item (title, amount, is_purchased)
    DELETE lists/{id}/items/{item_id}    delete item

This module deliberately has no Home Assistant imports so it can be tested
standalone.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

BASE_URL = "https://app.buymeapie.com"

_LOGGER = logging.getLogger(__name__)

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)
_LOCKED_RETRIES = 3

_HEADERS = {
    "Origin": BASE_URL,
    "Accept": "application/json, text/plain, */*",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.3 Safari/605.1.15"
    ),
}


class BuyMeAPieError(Exception):
    """Generic API error."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class BuyMeAPieAuthError(BuyMeAPieError):
    """E-mail or PIN rejected."""


class BuyMeAPieConnectionError(BuyMeAPieError):
    """Server not reachable or timed out."""


class BuyMeAPieClient:
    """Thin async wrapper around the Buy Me a Pie web API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        pin: str,
        *,
        base_url: str = BASE_URL,
        retry_delay: float = 1.0,
    ) -> None:
        self._session = session
        self._auth = aiohttp.BasicAuth(username, pin)
        self._base_url = base_url.rstrip("/")
        self._retry_delay = retry_delay
        self._logged_in = False

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}/{endpoint}"
        for attempt in range(1, _LOCKED_RETRIES + 1):
            try:
                async with self._session.request(
                    method,
                    url,
                    auth=self._auth,
                    headers=_HEADERS,
                    timeout=_REQUEST_TIMEOUT,
                    **kwargs,
                ) as resp:
                    status = resp.status
                    text = await resp.text()
            except (aiohttp.ClientError, TimeoutError) as err:
                raise BuyMeAPieConnectionError(
                    f"{method.upper()} {endpoint} failed: {err}"
                ) from err

            if status == 423 and attempt < _LOCKED_RETRIES:
                # Resource temporarily locked by a concurrent change: retry.
                _LOGGER.debug("%s %s locked (423), retry %s", method, endpoint, attempt)
                await asyncio.sleep(self._retry_delay * attempt)
                continue
            if status == 401:
                raise BuyMeAPieAuthError("E-mail or PIN rejected")
            if status not in (200, 201):
                raise BuyMeAPieError(
                    f"{method.upper()} {endpoint} returned {status}: {text[:200]}",
                    status=status,
                )
            if not text:
                return {}
            try:
                return json.loads(text)
            except json.JSONDecodeError as err:
                raise BuyMeAPieError(
                    f"{method.upper()} {endpoint} returned invalid JSON"
                ) from err

        raise BuyMeAPieError(f"{method.upper()} {endpoint} stayed locked (423)")

    async def _ensure_login(self) -> None:
        if not self._logged_in:
            await self.async_login()

    async def async_login(self) -> None:
        """Validate credentials (and let the server set its session cookie)."""
        await self._request("get", "bauth")
        self._logged_in = True

    # Lists

    async def async_get_lists(self) -> list[dict[str, Any]]:
        await self._ensure_login()
        return await self._request("get", "lists")

    async def async_create_list(self, name: str) -> dict[str, Any]:
        await self._ensure_login()
        return await self._request(
            "post",
            "lists",
            json={"items_not_purchased": 0, "items_purchased": 0, "name": name},
        )

    async def async_rename_list(
        self, list_id: str, name: str, emails: list[str] | None = None
    ) -> dict[str, Any]:
        await self._ensure_login()
        return await self._request(
            "put", f"lists/{list_id}", json={"name": name, "emails": emails or []}
        )

    async def async_delete_list(self, list_id: str) -> dict[str, Any]:
        await self._ensure_login()
        return await self._request("delete", f"lists/{list_id}")

    # Items

    async def async_get_items(self, list_id: str) -> list[dict[str, Any]]:
        await self._ensure_login()
        return await self._request("get", f"lists/{list_id}/items")

    async def async_add_item(
        self, list_id: str, title: str, amount: str = ""
    ) -> dict[str, Any]:
        await self._ensure_login()
        return await self._request(
            "post",
            f"lists/{list_id}/items",
            json={"amount": amount, "is_purchased": False, "title": title},
        )

    async def async_update_item(
        self,
        list_id: str,
        item_id: str,
        *,
        title: str,
        amount: str,
        is_purchased: bool,
    ) -> dict[str, Any]:
        await self._ensure_login()
        return await self._request(
            "put",
            f"lists/{list_id}/items/{item_id}",
            json={"title": title, "amount": amount, "is_purchased": is_purchased},
        )

    async def async_delete_item(self, list_id: str, item_id: str) -> dict[str, Any]:
        await self._ensure_login()
        return await self._request("delete", f"lists/{list_id}/items/{item_id}")
