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

SERVICE_PROMPT_SCHEMA = vol.Schema(
    {
        vol.Required("key"): str,
        vol.Required("prompt"): str,
        vol.Exclusive("phone", "recipient"): str,
        vol.Exclusive("contact_id", "recipient"): str,
        vol.Optional("ttl_seconds"): int,  # No default - empty means use default
        vol.Required("options"): vol.Any(str, [str]),
        vol.Optional("response_variable"): str,
        vol.Optional("keep_pending"): bool,  # No default - empty means false
    }
)

SERVICE_CLEAR_PENDING_SCHEMA = vol.Schema(
    {
        vol.Exclusive("phone", "recipient"): str,
        vol.Exclusive("contact_id", "recipient"): str,
        vol.Optional("key"): str,
    }
)

SERVICE_SET_CONTEXT_SCHEMA = vol.Schema(
    {
        vol.Exclusive("phone", "recipient"): str,
        vol.Exclusive("contact_id", "recipient"): str,
        vol.Required("data"): dict,
    }
)

SERVICE_WAIT_FOR_REPLY_SCHEMA = vol.Schema(
    {
        vol.Exclusive("phone", "recipient"): str,
        vol.Exclusive("contact_id", "recipient"): str,
        vol.Required("key"): str,
        vol.Required("response_variable"): str,
        vol.Optional("timeout"): int,
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
        _LOGGER.info("Sent message to %s", phone)

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

    key = data.get("key", "")
    prompt = data.get("prompt", "")
    ttl_seconds = data.get("ttl_seconds")  # None if not provided, will use default
    if ttl_seconds is None:
        ttl_seconds = 300  # Default value
    options = data.get("options")
    keep_pending = data.get("keep_pending", False)  # Default to False if not provided
    response_variable = data.get("response_variable")  # Variable name to store response

    if not key or not prompt:
        _LOGGER.error("Key and prompt are required")
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
        storage = TextNowStorage(hass, coordinator.entry.entry_id)
        pending_data = {
            "type": "choice",
            "created_at": dt_util.utcnow().isoformat(),
            "ttl_seconds": ttl_seconds,
            "keep_pending": keep_pending,
            "options": options,
        }

        # Store response_variable in pending data so we can update it when reply is received
        if response_variable:
            pending_data["response_variable"] = response_variable
        
        await storage.async_set_pending(phone, key, pending_data)
        _LOGGER.info("Sent prompt to %s with key %s (response_variable: %s)", phone, key, response_variable or "none")

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

    key = data.get("key")  # Optional

    storage = TextNowStorage(hass, coordinator.entry.entry_id)
    await storage.async_clear_pending(phone, key)
    _LOGGER.info("Cleared pending for %s%s", phone, f" key {key}" if key else "")


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


async def async_wait_for_reply(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Handle wait for reply service call.
    
    This service waits for a reply to a prompt and returns the response.
    Note: This is designed to be used with wait_for_trigger in automations.
    The actual waiting happens via the automation's wait_for_trigger action.
    
    This service can be used to validate that a pending expectation exists,
    but the actual waiting and variable setting should be done in the automation.
    """
    phone = await _resolve_phone_from_contact(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide contact_id")
        return None

    key = data.get("key", "")
    response_variable = data.get("response_variable", "")
    timeout = data.get("timeout")

    if not key or not response_variable:
        _LOGGER.error("Key and response_variable are required")
        return None

    # Check if pending expectation exists
    storage = TextNowStorage(hass, coordinator.entry.entry_id)
    pending = await storage.async_get_pending(phone)
    
    if key not in pending:
        _LOGGER.warning("No pending expectation found for key %s and phone %s", key, phone)
        return None

    pending_data = pending[key]
    
    # Get timeout from pending data if not provided
    if timeout is None:
        timeout = pending_data.get("ttl_seconds", 300)

    _LOGGER.info(
        "Waiting for reply to key %s from %s (timeout: %s seconds, response_variable: %s)",
        key, phone, timeout, response_variable
    )

    # Return info about the pending expectation
    # The actual waiting will be done by the automation's wait_for_trigger
    return {
        "key": key,
        "phone": phone,
        "response_variable": response_variable,
        "timeout": timeout,
        "pending_exists": True,
    }


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

