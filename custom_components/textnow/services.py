"""Services for TextNow integration."""
from __future__ import annotations

import logging
import os
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
        vol.Optional("message", default=""): str,
        vol.Exclusive("phone", "recipient"): str,
        vol.Exclusive("contact_id", "recipient"): str,
        vol.Optional("mms_image"): str,  # File path from file selector
        vol.Optional("voice_audio"): str,  # File path from file selector
    }
)



async def async_send_message(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> None:
    """Handle send message service call.
    
    Sends messages in order: SMS first, MMS second, voice message last.
    Only sends what is provided in the service call.
    """
    phone = await _resolve_phone_from_contact(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide contact_id")
        return

    message = data.get("message", "")
    mms_image = data.get("mms_image")
    voice_audio = data.get("voice_audio")
    
    # Determine what to send (SMS first, MMS second, voice last)
    send_sms = bool(message)  # Send SMS if message provided
    send_mms = bool(mms_image)
    send_voice = bool(voice_audio)
    
    if not send_sms and not send_mms and not send_voice:
        _LOGGER.error("Must provide message, mms_image, or voice_audio")
        return
    
    try:
        # Step 1: Send SMS first if message provided
        if send_sms:
            await coordinator.send_message(phone, message)
            _LOGGER.info("Sent SMS to %s", phone)
            await _update_sensor_outbound(hass, coordinator, phone)
        
        # Step 2: Send MMS second if image provided
        if send_mms:
            media_path = _resolve_file_path(hass, mms_image)
            if not media_path:
                _LOGGER.error("Could not resolve MMS image path: %s", mms_image)
                return
            # Use message as caption if provided, otherwise empty string
            caption = message if send_sms else (message or "")
            await coordinator.send_mms(phone, caption, media_path)
            _LOGGER.info("Sent MMS to %s", phone)
            await _update_sensor_outbound(hass, coordinator, phone)
        
        # Step 3: Send voice message last if audio provided
        if send_voice:
            audio_path = _resolve_file_path(hass, voice_audio)
            if not audio_path:
                _LOGGER.error("Could not resolve voice audio path: %s", voice_audio)
                return
            await coordinator.send_voice_message(phone, audio_path)
            _LOGGER.info("Sent voice message to %s", phone)
            await _update_sensor_outbound(hass, coordinator, phone)
            
    except Exception as e:
        _LOGGER.error("Failed to send message: %s", e)
        raise


def _resolve_file_path(hass: HomeAssistant, file_path: str) -> str | None:
    """Resolve file path from Home Assistant file selector.
    
    Handles:
    - /local/filename -> www folder
    - /config/path -> config folder
    - Absolute paths
    """
    if not file_path:
        return None
    
    # Normalize path separators
    file_path = file_path.replace("\\", "/")
    
    # Handle /local/ URLs (Home Assistant www folder)
    if file_path.startswith("/local/"):
        filename = file_path.replace("/local/", "").lstrip("/")
        www_path = hass.config.path("www")
        resolved_path = os.path.join(www_path, filename)
        _LOGGER.debug("Resolving /local/ path: %s -> %s", file_path, resolved_path)
        if os.path.exists(resolved_path):
            return resolved_path
        _LOGGER.warning("File not found at /local/ path: %s (checked: %s)", file_path, resolved_path)
    
    # Handle /config/ paths
    if file_path.startswith("/config/"):
        # Remove /config/ prefix and normalize
        relative_path = file_path.replace("/config/", "").lstrip("/")
        config_path = hass.config.config_dir
        resolved_path = os.path.join(config_path, relative_path)
        # Normalize path separators for the OS
        resolved_path = os.path.normpath(resolved_path)
        _LOGGER.debug("Resolving /config/ path: %s -> %s", file_path, resolved_path)
        if os.path.exists(resolved_path):
            return resolved_path
        _LOGGER.warning("File not found at /config/ path: %s (checked: %s)", file_path, resolved_path)
    
    # Handle absolute paths
    if os.path.isabs(file_path):
        normalized_path = os.path.normpath(file_path)
        _LOGGER.debug("Resolving absolute path: %s -> %s", file_path, normalized_path)
        if os.path.exists(normalized_path):
            return normalized_path
        _LOGGER.warning("File not found at absolute path: %s (checked: %s)", file_path, normalized_path)
    
    # Try relative to config directory
    config_path = hass.config.config_dir
    resolved_path = os.path.join(config_path, file_path.lstrip("/"))
    resolved_path = os.path.normpath(resolved_path)
    _LOGGER.debug("Resolving relative to config: %s -> %s", file_path, resolved_path)
    if os.path.exists(resolved_path):
        return resolved_path
    
    # Try as-is if it exists
    normalized_path = os.path.normpath(file_path)
    if os.path.exists(normalized_path):
        return normalized_path
    
    _LOGGER.error("Could not resolve file path: %s (tried multiple locations)", file_path)
    return None




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

