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
        vol.Optional("message_type", default="sms"): vol.In(["sms", "mms"]),
        vol.Optional("photo_url"): str,
    }
)

SERVICE_PROMPT_SCHEMA = vol.Schema(
    {
        vol.Required("prompt"): str,
        vol.Exclusive("phone", "recipient"): str,
        vol.Exclusive("contact_id", "recipient"): str,
        vol.Optional("ttl_seconds"): int,  # No default - empty means use default
        vol.Required("options"): vol.Any(str, [str]),
        vol.Optional("response_variable"): str,
    }
)

SERVICE_CLEAR_PENDING_SCHEMA = vol.Schema(
    {
        vol.Exclusive("phone", "recipient"): str,
        vol.Exclusive("contact_id", "recipient"): str,
    }
)

SERVICE_SET_CONTEXT_SCHEMA = vol.Schema(
    {
        vol.Exclusive("phone", "recipient"): str,
        vol.Exclusive("contact_id", "recipient"): str,
        vol.Required("data"): dict,
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

    message_type = data.get("message_type", "sms")
    photo_url = data.get("photo_url")

    try:
        if message_type == "sms":
            await coordinator.send_message(phone, message)
            _LOGGER.info("Sent SMS to %s", phone)
        elif message_type == "mms":
            if not photo_url:
                _LOGGER.error("photo_url is required for MMS")
                return
            await coordinator.send_mms(phone, message, photo_url, hass.config.path("www"))
            _LOGGER.info("Sent MMS to %s", phone)
        else:
            _LOGGER.error("Invalid message_type: %s", message_type)
            return

        # Update last_outbound for sensor
        await _update_sensor_outbound(hass, coordinator, phone)
    except Exception as e:
        _LOGGER.error("Failed to send message: %s", e)
        raise


async def async_prompt_message(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> None:
    """Handle prompt message service call."""
    phone = await _resolve_phone_from_contact(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide contact_id")
        return

    prompt = data.get("prompt", "")
    ttl_seconds = data.get("ttl_seconds")  # None if not provided, will use default
    if ttl_seconds is None:
        ttl_seconds = 300  # Default value
    options = data.get("options")
    response_variable = data.get("response_variable", "")  # Empty string if not provided
    # Treat empty string as None for response_variable
    if response_variable == "":
        response_variable = None

    if not prompt:
        _LOGGER.error("Prompt is required")
        return

    if not options:
        _LOGGER.error("Options are required for prompt service")
        return

    # Process options - always use choice type
    if isinstance(options, str):
        # Split by newlines or commas
        if "\n" in options:
            options = [opt.strip() for opt in options.split("\n") if opt.strip()]
        else:
            options = [opt.strip() for opt in options.split(",") if opt.strip()]
    elif not isinstance(options, list):
        _LOGGER.error("Options must be a list or string")
        return

    if not options:
        _LOGGER.error("At least one option is required")
        return

    # Build message with numbered choices
    message_lines = [prompt]
    for idx, option in enumerate(options, 1):
        message_lines.append(f"{idx}. {option}")
    message = "\n".join(message_lines)

    try:
        # Send the message
        await coordinator.send_message(phone, message)

        # Store pending expectation (always choice type)
        # Use a default key since we removed the key parameter
        # We'll use phone number as the key (one pending per phone)
        storage = TextNowStorage(hass, coordinator.entry.entry_id)
        pending_data = {
            "type": "choice",
            "created_at": dt_util.utcnow().isoformat(),
            "ttl_seconds": ttl_seconds,
            "options": options,
        }

        # Store response_variable in pending data so we can update it when reply is received
        if response_variable:
            pending_data["response_variable"] = response_variable
        
        # Use "default" as the key since we removed the key parameter
        # This means only one pending prompt per phone at a time
        await storage.async_set_pending(phone, "default", pending_data)
        _LOGGER.info("Sent prompt to %s (response_variable: %s)", phone, response_variable or "none")

        # Update last_outbound for sensor
        await _update_sensor_outbound(hass, coordinator, phone)
    except Exception as e:
        _LOGGER.error("Failed to send prompt: %s", e)
        raise


async def async_clear_pending(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> None:
    """Handle clear pending service call."""
    phone = await _resolve_phone_from_contact(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide contact_id")
        return

    storage = TextNowStorage(hass, coordinator.entry.entry_id)
    # Clear all pending for this phone (no key needed anymore)
    await storage.async_clear_pending(phone, None)
    _LOGGER.info("Cleared pending for %s", phone)


async def async_set_context(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> None:
    """Handle set context service call."""
    phone = await _resolve_phone_from_contact(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide contact_id")
        return

    context_data = data.get("data", {})
    if not isinstance(context_data, dict):
        _LOGGER.error("Data must be a dictionary")
        return

    storage = TextNowStorage(hass, coordinator.entry.entry_id)
    await storage.async_set_context(phone, context_data)
    _LOGGER.info("Set context for %s", phone)


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

