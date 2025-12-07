"""Storage helper for TextNow integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class TextNowStorage:
    """Handle storage for TextNow integration."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize storage."""
        self.hass = hass
        self.entry_id = entry_id
        self._store = storage.Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")

    async def async_load(self) -> dict[str, Any]:
        """Load data from storage."""
        data = await self._store.async_load()
        if data is None:
            return {
                "contacts": {},
                "pending": {},
                "context": {},
                "processed_message_ids": set(),
            }
        # Convert processed_message_ids list back to set
        if "processed_message_ids" in data and isinstance(
            data["processed_message_ids"], list
        ):
            data["processed_message_ids"] = set(data["processed_message_ids"])
        return data

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save data to storage."""
        # Convert processed_message_ids set to list for JSON serialization
        save_data = data.copy()
        if "processed_message_ids" in save_data and isinstance(
            save_data["processed_message_ids"], set
        ):
            save_data["processed_message_ids"] = list(save_data["processed_message_ids"])
        await self._store.async_save(save_data)

    async def async_get_contacts(self) -> dict[str, dict[str, Any]]:
        """Get all contacts."""
        data = await self.async_load()
        return data.get("contacts", {})

    async def async_save_contact(
        self, contact_id: str, name: str, phone: str
    ) -> None:
        """Save a contact."""
        data = await self.async_load()
        data["contacts"][contact_id] = {"name": name, "phone": phone}
        await self.async_save(data)

    async def async_delete_contact(self, contact_id: str) -> None:
        """Delete a contact."""
        data = await self.async_load()
        if contact_id in data.get("contacts", {}):
            # Get phone before deleting
            phone = data["contacts"][contact_id].get("phone")
            del data["contacts"][contact_id]
            # Also clean up pending and context for this contact
            if phone:
                if phone in data.get("pending", {}):
                    del data["pending"][phone]
                if phone in data.get("context", {}):
                    del data["context"][phone]
            await self.async_save(data)

    async def async_get_pending(self, phone: str) -> dict[str, Any]:
        """Get pending expectations for a phone."""
        data = await self.async_load()
        return data.get("pending", {}).get(phone, {})

    async def async_set_pending(
        self, phone: str, key: str, pending_data: dict[str, Any]
    ) -> None:
        """Set pending expectation for a phone."""
        data = await self.async_load()
        if "pending" not in data:
            data["pending"] = {}
        if phone not in data["pending"]:
            data["pending"][phone] = {}
        data["pending"][phone][key] = pending_data
        await self.async_save(data)

    async def async_clear_pending(self, phone: str, key: str | None = None) -> None:
        """Clear pending expectation(s) for a phone."""
        data = await self.async_load()
        if "pending" not in data:
            data["pending"] = {}
        if phone in data["pending"]:
            if key is None:
                data["pending"][phone] = {}
            elif key in data["pending"][phone]:
                del data["pending"][phone][key]
        await self.async_save(data)

    async def async_get_context(self, phone: str) -> dict[str, Any]:
        """Get context for a phone."""
        data = await self.async_load()
        return data.get("context", {}).get(phone, {})

    async def async_set_context(self, phone: str, context_data: dict[str, Any]) -> None:
        """Set context for a phone (merge)."""
        data = await self.async_load()
        if "context" not in data:
            data["context"] = {}
        if phone not in data["context"]:
            data["context"][phone] = {}
        data["context"][phone].update(context_data)
        await self.async_save(data)

    async def async_add_processed_message_id(self, message_id: str) -> None:
        """Add a processed message ID."""
        data = await self.async_load()
        if "processed_message_ids" not in data:
            data["processed_message_ids"] = set()
        data["processed_message_ids"].add(message_id)
        await self.async_save(data)

    async def async_is_message_processed(self, message_id: str) -> bool:
        """Check if a message ID has been processed."""
        data = await self.async_load()
        processed = data.get("processed_message_ids", set())
        return message_id in processed

