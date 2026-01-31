"""Services for TextNow integration."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import datetime
from typing import Any
from urllib.parse import quote

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util
from homeassistant.helpers import config_validation as cv
import voluptuous as vol
import aiohttp

from .const import (
    DOMAIN,
    EVENT_REPLY_PARSED,
    ATTR_PHONE,
    ATTR_CONTACT_ID,
    DEFAULT_MENU_TIMEOUT,
    DEFAULT_NUMBER_FORMAT,
    DEFAULT_MENU_HEADER,
    DEFAULT_MENU_FOOTER,
)
from .coordinator import TextNowDataUpdateCoordinator
from .storage import TextNowStorage

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_SCHEMA = vol.Schema(
    {
        vol.Optional("message", default=""): str,
        vol.Optional("contact_id"): str,  # Entity selector dropdown
        vol.Optional("contact_from_trigger"): str,  # Template field for trigger variable
        vol.Optional("phone"): str,  # Direct phone number (legacy)
        vol.Optional("mms_image"): str,  # File path from file selector
        vol.Optional("voice_audio"): str,  # File path from file selector
    }
)

SERVICE_SEND_MENU_SCHEMA = vol.Schema(
    {
        vol.Optional("contact_id"): str,  # Entity selector dropdown
        vol.Optional("contact_from_trigger"): str,  # Template field for trigger variable
        vol.Required("options"): str,  # Multiline text, one option per line
        vol.Optional("include_header", default=True): bool,
        vol.Optional("header", default=DEFAULT_MENU_HEADER): str,
        vol.Optional("include_footer", default=True): bool,
        vol.Optional("footer", default=DEFAULT_MENU_FOOTER): str,
        vol.Optional("timeout", default=DEFAULT_MENU_TIMEOUT): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=3600)
        ),
        vol.Optional("number_format", default=DEFAULT_NUMBER_FORMAT): str,
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
            file_data = await _resolve_file_data(hass, mms_image)
            if not file_data:
                _LOGGER.error("Could not resolve MMS image: %s", mms_image)
                return
            # Extract filename for content type detection
            filename = os.path.basename(mms_image) if mms_image else "image.jpg"
            # Use message as caption if provided, otherwise empty string
            caption = message if send_sms else (message or "")
            await coordinator.send_mms(phone, caption, file_data, filename)
            _LOGGER.info("Sent MMS to %s", phone)
            await _update_sensor_outbound(hass, coordinator, phone)
        
        # Step 3: Send voice message last if audio provided
        if send_voice:
            file_data = await _resolve_file_data(hass, voice_audio)
            if not file_data:
                _LOGGER.error("Could not resolve voice audio: %s", voice_audio)
                return
            await coordinator.send_voice_message(phone, file_data)
            _LOGGER.info("Sent voice message to %s", phone)
            await _update_sensor_outbound(hass, coordinator, phone)
            
    except Exception as e:
        _LOGGER.error("Failed to send message: %s", e)
        raise


async def _resolve_file_data(hass: HomeAssistant, file_path: str) -> bytes | None:
    """Resolve file data from Home Assistant path or URL.
    
    Handles:
    - /local/filename -> downloads from Home Assistant URL or reads from www folder
    - /config/path -> downloads from Home Assistant URL or reads from config folder
    - Absolute paths -> reads directly
    - Home Assistant URLs -> downloads from URL
    
    Returns file data as bytes, or None if file cannot be resolved.
    """
    if not file_path:
        return None
    
    # Normalize path separators
    file_path = file_path.replace("\\", "/")
    
    # Try to resolve as local file first
    local_path = _resolve_file_path(hass, file_path)
    if local_path:
        # Check if file exists in executor to avoid blocking
        file_exists = await hass.async_add_executor_job(os.path.exists, local_path)
        if file_exists:
            _LOGGER.debug("Reading file from local path: %s", local_path)
            try:
                # Read file in executor to avoid blocking event loop
                def read_file():
                    with open(local_path, "rb") as f:
                        return f.read()
                return await hass.async_add_executor_job(read_file)
            except Exception as e:
                _LOGGER.warning("Failed to read local file %s: %s", local_path, e)
    
    # If local file doesn't exist, try to download from Home Assistant URL
    ha_url = _build_home_assistant_file_url(hass, file_path)
    if ha_url:
        _LOGGER.debug("Downloading file from Home Assistant URL: %s", ha_url)
        try:
            # Use Home Assistant's internal request helper if available
            # Otherwise use aiohttp with proper headers
            from homeassistant.helpers import network
            
            # Try to get the internal URL for local requests
            try:
                internal_url = hass.config.internal_url or "http://homeassistant.local:8123"
                # If the URL is internal, we can access it directly
                if ha_url.startswith(internal_url) or ha_url.startswith("http://homeassistant.local"):
                    # For internal requests, use aiohttp without auth (local network)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(ha_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                            if response.status == 200:
                                file_data = await response.read()
                                _LOGGER.debug("Successfully downloaded file from URL: %s (%d bytes)", ha_url, len(file_data))
                                return file_data
                            else:
                                _LOGGER.warning("Failed to download file from URL %s: status %s", ha_url, response.status)
                else:
                    # For external URLs, might need authentication
                    async with aiohttp.ClientSession() as session:
                        async with session.get(ha_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                            if response.status == 200:
                                file_data = await response.read()
                                _LOGGER.debug("Successfully downloaded file from URL: %s (%d bytes)", ha_url, len(file_data))
                                return file_data
                            else:
                                _LOGGER.warning("Failed to download file from URL %s: status %s", ha_url, response.status)
            except Exception as e:
                _LOGGER.warning("Error downloading file from URL %s: %s", ha_url, e)
        except Exception as e:
            _LOGGER.warning("Error downloading file from URL %s: %s", ha_url, e)
    
    _LOGGER.error("Could not resolve file: %s (tried local path and Home Assistant URL)", file_path)
    return None


def _build_home_assistant_file_url(hass: HomeAssistant, file_path: str) -> str | None:
    """Build Home Assistant file URL from internal path.
    
    Converts:
    - /local/filename -> {base_url}/local/filename (served directly)
    - /config/path -> tries to construct URL (may need adjustment)
    """
    if not file_path:
        return None
    
    file_path = file_path.replace("\\", "/")
    
    # Get Home Assistant base URL
    try:
        # Try to get the base URL from the config
        base_url = str(hass.config.api.base_url) if hasattr(hass.config.api, 'base_url') and hass.config.api.base_url else None
        if not base_url:
            # Fallback to internal URL
            base_url = str(hass.config.internal_url) if hass.config.internal_url else "http://homeassistant.local:8123"
        # Remove trailing slash if present
        base_url = base_url.rstrip("/")
    except Exception:
        base_url = "http://homeassistant.local:8123"
    
    # Handle /local/ paths - served directly
    if file_path.startswith("/local/"):
        filename = file_path.replace("/local/", "").lstrip("/")
        # /local/ files are served directly
        return f"{base_url}/local/{filename}"
    
    # Handle /config/ paths
    if file_path.startswith("/config/"):
        relative_path = file_path.replace("/config/", "").lstrip("/")
        # Try direct file API first
        # For Supervisor/OS installations, might need hassio_ingress format
        # But for regular HA, try the file API
        hassio_path = f"/homeassistant/config/{relative_path}"
        return f"{base_url}/api/file?filename={quote(hassio_path)}"
    
    # If it's already a URL, return as-is
    if file_path.startswith("http://") or file_path.startswith("https://"):
        return file_path
    
    return None


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
    """Resolve phone number from contact_id or contact_from_trigger.
    
    Priority:
    1. contact_from_trigger (template field for trigger variables)
    2. contact_id (entity selector dropdown)
    3. phone (direct phone number - legacy)
    """
    # Check contact_from_trigger first (template field)
    contact_id = data.get("contact_from_trigger")
    
    # If contact_from_trigger is empty or not provided, fall back to contact_id
    if not contact_id or not contact_id.strip():
        contact_id = data.get("contact_id")
    
    # If still nothing, check for direct phone number
    if not contact_id or not contact_id.strip():
        phone = data.get("phone")
        if phone:
            _LOGGER.debug("Using direct phone number: %s", phone)
            return phone
    
    if not contact_id:
        _LOGGER.error("No contact_id, contact_from_trigger, or phone provided in service call")
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


def _build_menu_text(
    header: str,
    options: list[str],
    footer: str,
    number_format: str = DEFAULT_NUMBER_FORMAT,
) -> str:
    """Build formatted menu text from options.
    
    Args:
        header: Text before the menu options
        options: List of menu option strings
        footer: Text after the menu options
        number_format: Format string for each option (uses {n} and {option})
    
    Returns:
        Formatted menu text string
    """
    lines = []
    
    if header:
        lines.append(header)
        lines.append("")  # Empty line after header
    
    for idx, option in enumerate(options, start=1):
        formatted_option = number_format.format(n=idx, option=option)
        lines.append(formatted_option)
    
    if footer:
        lines.append("")  # Empty line before footer
        lines.append(footer)
    
    return "\n".join(lines)


def _parse_options_text(options_text: str) -> list[str]:
    """Parse multiline options text into a list of options.
    
    Each non-empty line becomes an option.
    """
    lines = options_text.strip().split("\n")
    return [line.strip() for line in lines if line.strip()]


async def async_send_menu(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator, data: dict[str, Any]
) -> dict[str, Any]:
    """Handle send menu service call.
    
    Builds a numbered menu from options, sends it via SMS, and waits for response.
    Returns response data for use with response_variable.
    """
    phone = await _resolve_phone_from_contact(hass, coordinator, data)
    if not phone:
        _LOGGER.error("Must provide valid contact_id for send_menu")
        return {
            "timed_out": True,
            "error": "Invalid contact_id",
        }

    contact_id = data.get("contact_id", "")
    options_text = data.get("options", "")
    include_header = data.get("include_header", True)
    header = data.get("header", DEFAULT_MENU_HEADER) if include_header else ""
    include_footer = data.get("include_footer", True)
    footer = data.get("footer", DEFAULT_MENU_FOOTER) if include_footer else ""
    timeout = data.get("timeout", DEFAULT_MENU_TIMEOUT)
    number_format = data.get("number_format", DEFAULT_NUMBER_FORMAT)

    # Parse options from multiline text
    options = _parse_options_text(options_text)
    
    if not options:
        _LOGGER.error("Must provide at least one option for send_menu")
        return {
            "timed_out": True,
            "error": "No options provided",
        }

    # Build menu text
    menu_text = _build_menu_text(header, options, footer, number_format)
    
    try:
        # Send the menu via SMS
        await coordinator.send_message(phone, menu_text)
        _LOGGER.info("Sent menu to %s with %d options", phone, len(options))
        await _update_sensor_outbound(hass, coordinator, phone)
        
        # Register pending expectation for choice response
        storage = TextNowStorage(hass, coordinator.entry.entry_id)
        pending_data = {
            "type": "choice",
            "options": options,
            "created_at": dt_util.utcnow().isoformat(),
            "ttl_seconds": timeout,
        }
        await storage.async_set_pending(phone, "menu", pending_data)
        _LOGGER.debug("Registered menu pending expectation for %s", phone)
        
    except Exception as e:
        _LOGGER.error("Failed to send menu: %s", e)
        return {
            "timed_out": True,
            "error": str(e),
        }

    # Now wait for response
    response_future: asyncio.Future[dict[str, Any]] = asyncio.Future()
    unsub_callback = None

    @callback
    def handle_reply_event(event) -> None:
        """Handle reply parsed event."""
        event_data = event.data
        event_phone = event_data.get(ATTR_PHONE, "")
        
        # Check if this reply is for our phone
        if event_phone != phone:
            return
        
        # Build response data
        response_data = {
            "option": int(event_data.get("response_number", event_data.get("option_index", 0) + 1)),
            "option_index": event_data.get("option_index", 0),
            "value": event_data.get("value", ""),
            "raw_text": event_data.get("raw_text", ""),
            "phone": event_phone,
            "contact_id": event_data.get(ATTR_CONTACT_ID, contact_id),
            "timed_out": False,
        }
        
        # Resolve the future if not already done
        if not response_future.done():
            response_future.set_result(response_data)

    # Subscribe to reply parsed events
    unsub_callback = hass.bus.async_listen(EVENT_REPLY_PARSED, handle_reply_event)

    try:
        # Wait for response with timeout
        result = await asyncio.wait_for(response_future, timeout=timeout)
        _LOGGER.info("Received response from %s: option %s", phone, result.get("option"))
        return result
        
    except asyncio.TimeoutError:
        _LOGGER.info("Menu response timed out for %s after %d seconds", phone, timeout)
        return {
            "option": 0,
            "option_index": -1,
            "value": "",
            "raw_text": "",
            "phone": phone,
            "contact_id": contact_id,
            "timed_out": True,
        }
        
    finally:
        # Always unsubscribe from events
        if unsub_callback:
            unsub_callback()

