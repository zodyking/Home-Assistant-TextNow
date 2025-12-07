"""WebSocket API for TextNow panel."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .phone_utils import format_phone_number
from .storage import TextNowStorage

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up WebSocket API."""
    websocket_api.async_register_command(hass, websocket_contacts_list)
    websocket_api.async_register_command(hass, websocket_contacts_add)
    websocket_api.async_register_command(hass, websocket_contacts_update)
    websocket_api.async_register_command(hass, websocket_contacts_delete)
    websocket_api.async_register_command(hass, websocket_send_test)


@websocket_api.websocket_command(
    {
        "type": "textnow/contacts_list",
        vol.Required("entry_id"): str,
    }
)
@websocket_api.async_response
async def websocket_contacts_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """List all contacts for an entry."""
    entry_id = msg["entry_id"]
    
    # Verify entry exists
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return
    
    storage = TextNowStorage(hass, entry_id)
    contacts = await storage.async_get_contacts()
    
    # Format contacts for frontend
    result = []
    for contact_id, contact_data in contacts.items():
        result.append({
            "id": contact_id,
            "name": contact_data.get("name", ""),
            "phone": contact_data.get("phone", ""),
            "enabled": True,  # All contacts are enabled by default
        })
    
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        "type": "textnow/contacts_add",
        vol.Required("entry_id"): str,
        vol.Required("name"): str,
        vol.Required("phone"): str,
    }
)
@websocket_api.async_response
async def websocket_contacts_add(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add a new contact."""
    entry_id = msg["entry_id"]
    name = msg["name"].strip()
    phone = msg["phone"].strip()
    
    if not name or not phone:
        connection.send_error(msg["id"], "invalid_format", "Name and phone are required")
        return
    
    # Verify entry exists
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return
    
    # Format phone number
    try:
        formatted_phone = format_phone_number(phone)
    except ValueError as e:
        connection.send_error(msg["id"], "invalid_format", str(e))
        return
    
    storage = TextNowStorage(hass, entry_id)
    
    # Generate contact_id if not provided
    contact_id = f"contact_{name.lower().replace(' ', '_')}"
    contacts = await storage.async_get_contacts()
    counter = 1
    original_id = contact_id
    while contact_id in contacts:
        contact_id = f"{original_id}_{counter}"
        counter += 1
    
    await storage.async_save_contact(contact_id, name, formatted_phone)
    
    # Fire event for sensor update
    hass.bus.async_fire(
        f"{DOMAIN}_contact_added",
        {"contact_id": contact_id, "name": name, "phone": formatted_phone},
    )
    
    connection.send_result(msg["id"], {
        "id": contact_id,
        "name": name,
        "phone": formatted_phone,
        "enabled": True,
    })


@websocket_api.websocket_command(
    {
        "type": "textnow/contacts_update",
        vol.Required("entry_id"): str,
        vol.Required("id"): str,
        vol.Required("name"): str,
        vol.Required("phone"): str,
        vol.Optional("enabled", default=True): bool,
    }
)
@websocket_api.async_response
async def websocket_contacts_update(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update an existing contact."""
    entry_id = msg["entry_id"]
    contact_id = msg["id"]
    name = msg["name"].strip()
    phone = msg["phone"].strip()
    
    if not name or not phone:
        connection.send_error(msg["id"], "invalid_format", "Name and phone are required")
        return
    
    # Verify entry exists
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return
    
    storage = TextNowStorage(hass, entry_id)
    contacts = await storage.async_get_contacts()
    
    if contact_id not in contacts:
        connection.send_error(msg["id"], "not_found", "Contact not found")
        return
    
    # Format phone number
    try:
        formatted_phone = format_phone_number(phone)
    except ValueError as e:
        connection.send_error(msg["id"], "invalid_format", str(e))
        return
    
    await storage.async_save_contact(contact_id, name, formatted_phone)
    
    connection.send_result(msg["id"], {
        "id": contact_id,
        "name": name,
        "phone": formatted_phone,
        "enabled": msg.get("enabled", True),
    })


@websocket_api.websocket_command(
    {
        "type": "textnow/contacts_delete",
        vol.Required("entry_id"): str,
        vol.Required("id"): str,
    }
)
@websocket_api.async_response
async def websocket_contacts_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a contact."""
    entry_id = msg["entry_id"]
    contact_id = msg["id"]
    
    # Verify entry exists
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return
    
    storage = TextNowStorage(hass, entry_id)
    contacts = await storage.async_get_contacts()
    
    if contact_id not in contacts:
        connection.send_error(msg["id"], "not_found", "Contact not found")
        return
    
    await storage.async_delete_contact(contact_id)
    
    # Fire event for sensor removal
    hass.bus.async_fire(
        f"{DOMAIN}_contact_deleted",
        {"contact_id": contact_id},
    )
    
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command(
    {
        "type": "textnow/send_test",
        vol.Required("entry_id"): str,
        vol.Optional("id"): str,  # contact_id
        vol.Optional("phone"): str,  # direct phone number
        vol.Required("message"): str,
    }
)
@websocket_api.async_response
async def websocket_send_test(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send a test message."""
    entry_id = msg["entry_id"]
    contact_id = msg.get("id")
    phone = msg.get("phone")
    message = msg["message"].strip()
    
    if not message:
        connection.send_error(msg["id"], "invalid_format", "Message is required")
        return
    
    # Verify entry exists
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return
    
    # Get coordinator
    if DOMAIN not in hass.data or entry_id not in hass.data[DOMAIN]:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    
    coordinator = hass.data[DOMAIN][entry_id]
    
    # Resolve phone number
    if contact_id:
        storage = TextNowStorage(hass, entry_id)
        contacts = await storage.async_get_contacts()
        if contact_id not in contacts:
            connection.send_error(msg["id"], "not_found", "Contact not found")
            return
        phone = contacts[contact_id]["phone"]
    elif phone:
        # Format phone number if provided directly
        try:
            phone = format_phone_number(phone)
        except ValueError as e:
            connection.send_error(msg["id"], "invalid_format", str(e))
            return
    else:
        connection.send_error(msg["id"], "invalid_format", "Either id or phone must be provided")
        return
    
    # Send message
    try:
        await coordinator.send_message(phone, message)
        connection.send_result(msg["id"], {"success": True, "phone": phone})
    except Exception as e:
        _LOGGER.error("Failed to send test message: %s", e)
        connection.send_error(msg["id"], "send_failed", str(e))

