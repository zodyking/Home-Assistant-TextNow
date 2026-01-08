"""Services for TextNow integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import DOMAIN
from .coordinator import TextNowDataUpdateCoordinator
from .storage import TextNowStorage

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_SCHEMA = vol.Schema(
    {
        vol.Required("message"): str,
        vol.Exclusive("phone", "recipient"): str,
        vol.Exclusive("contact_id", "recipient"): str,
    }
)



async def async_send_message(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> None:
    """Handle send message service call."""
    phone = await _resolve_phone_from_contact(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide contact_id")
        return

    message = data.get("message", "")
    if not message:
        _LOGGER.error("Message is required")
        return

    try:
        await coordinator.send_message(phone, message)
        _LOGGER.info("Sent SMS to %s", phone)

        # Update last_outbound for sensor
        await _update_sensor_outbound(hass, coordinator, phone)
    except Exception as e:
        _LOGGER.error("Failed to send message: %s", e)
        raise




async def _resolve_phone_from_contact(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> str | None:
    """Resolve phone number from contact_id (entity_id or contact_id)."""
    contact_id = data.get("contact_id")
    if not contact_id:
        _LOGGER.error("No contact_id provided in service call")
        return None

    _LOGGER.debug("Resolving phone for contact_id: %s", contact_id)

    # First, try to get phone from entity state if it's an entity_id
    if contact_id.startswith("sensor."):
        state = hass.states.get(contact_id)
        if state and state.attributes.get("phone"):
            phone = state.attributes["phone"]
            _LOGGER.info("Resolved phone %s from entity %s", phone, contact_id)
            return phone
        # Extract contact_id from entity_id (sensor.textnow_contact_xxx -> contact_xxx)
        if contact_id.startswith("sensor.textnow_"):
            contact_id = contact_id.replace("sensor.textnow_", "")
            _LOGGER.debug("Extracted contact_id: %s from entity_id", contact_id)

    # Get phone from storage
    storage = TextNowStorage(hass, coordinator.entry.entry_id)
    contacts = await storage.async_get_contacts()
    _LOGGER.debug("Available contacts: %s", list(contacts.keys()))
    
    if contact_id in contacts:
        phone = contacts[contact_id]["phone"]
        _LOGGER.info("Resolved phone %s from contact_id %s", phone, contact_id)
        return phone

    _LOGGER.error("Contact not found: %s (searched in %d contacts)", contact_id, len(contacts))
    _LOGGER.error("Available contact_ids: %s", list(contacts.keys()))
    return None


async def _update_sensor_outbound(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, phone: str
) -> None:
    """Update sensor last_outbound timestamp."""
    # Fire event to update sensor
    from homeassistant.util import dt as dt_util
    hass.bus.async_fire(
        f"{DOMAIN}_message_sent",
        {
            "phone": phone,
            "timestamp": dt_util.utcnow().isoformat(),
        },
    )

