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
        vol.Required("type"): vol.In(["choice", "text", "number", "boolean"]),
        vol.Exclusive("phone", "recipient"): str,
        vol.Exclusive("contact_id", "recipient"): str,
        vol.Optional("ttl_seconds", default=300): int,
        vol.Optional("options"): vol.Any(str, [str]),
        vol.Optional("regex"): str,
        vol.Optional("keep_pending", default=False): bool,
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


async def async_send_message(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> None:
    """Handle send message service call."""
    phone = await _resolve_phone(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide either phone or contact_id")
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
    phone = await _resolve_phone(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide either phone or contact_id")
        return

    key = data.get("key", "")
    prompt = data.get("prompt", "")
    prompt_type = data.get("type", "text")
    ttl_seconds = data.get("ttl_seconds", 300)
    options = data.get("options")
    regex = data.get("regex")
    keep_pending = data.get("keep_pending", False)

    if not key or not prompt:
        _LOGGER.error("Key and prompt are required")
        return

    # Process options
    if options:
        if isinstance(options, str):
            # Split by newlines or commas
            if "\n" in options:
                options = [opt.strip() for opt in options.split("\n") if opt.strip()]
            else:
                options = [opt.strip() for opt in options.split(",") if opt.strip()]
        elif not isinstance(options, list):
            options = None

    # Build message for choice type
    if prompt_type == "choice" and options:
        message_lines = [prompt]
        for idx, option in enumerate(options, 1):
            message_lines.append(f"{idx}. {option}")
        message = "\n".join(message_lines)
    else:
        message = prompt

    try:
        # Send the message
        await coordinator.send_message(phone, message)

        # Store pending expectation
        storage = TextNowStorage(hass, coordinator.entry.entry_id)
        pending_data = {
            "type": prompt_type,
            "created_at": dt_util.utcnow().isoformat(),
            "ttl_seconds": ttl_seconds,
            "keep_pending": keep_pending,
        }
        if options:
            pending_data["options"] = options
        if regex:
            pending_data["regex"] = regex

        await storage.async_set_pending(phone, key, pending_data)
        _LOGGER.info("Sent prompt to %s with key %s", phone, key)

        # Update last_outbound for sensor
        await _update_sensor_outbound(hass, coordinator, phone)
    except Exception as e:
        _LOGGER.error("Failed to send prompt: %s", e)
        raise


async def async_clear_pending(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> None:
    """Handle clear pending service call."""
    phone = await _resolve_phone(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide either phone or contact_id")
        return

    key = data.get("key")  # Optional

    storage = TextNowStorage(hass, coordinator.entry.entry_id)
    await storage.async_clear_pending(phone, key)
    _LOGGER.info("Cleared pending for %s%s", phone, f" key {key}" if key else "")


async def async_set_context(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> None:
    """Handle set context service call."""
    phone = await _resolve_phone(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide either phone or contact_id")
        return

    context_data = data.get("data", {})
    if not isinstance(context_data, dict):
        _LOGGER.error("Data must be a dictionary")
        return

    storage = TextNowStorage(hass, coordinator.entry.entry_id)
    await storage.async_set_context(phone, context_data)
    _LOGGER.info("Set context for %s", phone)


async def _resolve_phone(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> str | None:
    """Resolve phone number from phone or contact_id."""
    if "phone" in data:
        return data["phone"]

    if "contact_id" in data:
        contact_id = data["contact_id"]
        storage = TextNowStorage(hass, coordinator.entry.entry_id)
        contacts = await storage.async_get_contacts()
        if contact_id in contacts:
            return contacts[contact_id]["phone"]

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

