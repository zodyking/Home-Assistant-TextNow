"""Sensor platform for TextNow."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ATTR_PHONE,
    ATTR_LAST_INBOUND,
    ATTR_LAST_INBOUND_TS,
    ATTR_LAST_OUTBOUND,
    ATTR_LAST_OUTBOUND_TS,
    ATTR_PENDING,
    ATTR_CONTEXT,
    ATTR_TEXT,
    ATTR_TIMESTAMP,
    EVENT_MESSAGE_RECEIVED,
    EVENT_REPLY_PARSED,
)
from .coordinator import TextNowDataUpdateCoordinator
from .storage import TextNowStorage

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TextNow sensors from a config entry."""
    coordinator: TextNowDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    storage_helper = TextNowStorage(hass, entry.entry_id)

    # Load contacts and create sensors
    contacts = await storage_helper.async_get_contacts()
    entities = [
        TextNowContactSensor(coordinator, storage_helper, contact_id, contact_data)
        for contact_id, contact_data in contacts.items()
    ]

    async_add_entities(entities)

    # Listen for new contacts being added
    async def contact_added_listener(event):
        """Handle contact added event."""
        contact_id = event.data.get("contact_id")
        name = event.data.get("name")
        phone = event.data.get("phone")
        if contact_id and name and phone:
            entity = TextNowContactSensor(
                coordinator, storage_helper, contact_id, {"name": name, "phone": phone}
            )
            async_add_entities([entity])

    hass.bus.async_listen(f"{DOMAIN}_contact_added", contact_added_listener)


class TextNowContactSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TextNow contact sensor."""

    def __init__(
        self,
        coordinator: TextNowDataUpdateCoordinator,
        storage: TextNowStorage,
        contact_id: str,
        contact_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._storage = storage
        self._contact_id = contact_id
        self._name = contact_data.get("name", contact_id)
        self._phone = contact_data.get("phone", "")
        self._last_inbound = None
        self._last_inbound_ts = None
        self._last_outbound = None
        self._last_outbound_ts = None
        self._pending = {}
        self._context = {}

        # Listen for message events
        self._unsub_message = None
        self._unsub_reply = None
        self._unsub_sent = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"textnow_{self._contact_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"TextNow {self._name}"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self._last_inbound:
            return self._last_inbound
        return "No messages"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            ATTR_PHONE: self._phone,
            ATTR_LAST_INBOUND: self._last_inbound,
            ATTR_LAST_INBOUND_TS: self._last_inbound_ts,
            ATTR_LAST_OUTBOUND: self._last_outbound,
            ATTR_LAST_OUTBOUND_TS: self._last_outbound_ts,
            ATTR_PENDING: self._pending,
            ATTR_CONTEXT: self._context,
        }

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Load initial state
        await self._update_state()

        # Listen for message events
        self._unsub_message = self.hass.bus.async_listen(
            EVENT_MESSAGE_RECEIVED, self._handle_message_received
        )
        self._unsub_reply = self.hass.bus.async_listen(
            EVENT_REPLY_PARSED, self._handle_reply_parsed
        )
        self._unsub_sent = self.hass.bus.async_listen(
            f"{DOMAIN}_message_sent", self._handle_message_sent
        )

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        if self._unsub_message:
            self._unsub_message()
        if self._unsub_reply:
            self._unsub_reply()
        if self._unsub_sent:
            self._unsub_sent()
        await super().async_will_remove_from_hass()

    async def _handle_message_received(self, event) -> None:
        """Handle message received event."""
        if event.data.get(ATTR_PHONE) == self._phone:
            self._last_inbound = event.data.get(ATTR_TEXT, "")
            self._last_inbound_ts = event.data.get(ATTR_TIMESTAMP, "")
            await self._update_state()
            self.async_write_ha_state()

    async def _handle_reply_parsed(self, event) -> None:
        """Handle reply parsed event."""
        if event.data.get(ATTR_PHONE) == self._phone:
            await self._update_state()
            self.async_write_ha_state()

    async def _handle_message_sent(self, event) -> None:
        """Handle message sent event."""
        if event.data.get("phone") == self._phone:
            self._last_outbound = "Sent"
            self._last_outbound_ts = event.data.get("timestamp", "")
            self.async_write_ha_state()

    async def _update_state(self) -> None:
        """Update sensor state from storage."""
        self._pending = await self._storage.async_get_pending(self._phone)
        self._context = await self._storage.async_get_context(self._phone)

        # Try to get last inbound/outbound from storage if not set
        # This is a simplified approach - you might want to store these in storage
        # For now, we rely on events to update them

    async def async_update_last_outbound(self) -> None:
        """Update last outbound timestamp."""
        self._last_outbound = "Sent"
        self._last_outbound_ts = dt_util.utcnow().isoformat()
        self.async_write_ha_state()

