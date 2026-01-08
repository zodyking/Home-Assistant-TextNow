"""TextNow services."""
import logging
import voluptuous as vol
from typing import Any
from homeassistant.core import HomeAssistant, ServiceCall
from .const import DOMAIN
from .coordinator import TextNowDataUpdateCoordinator
from .storage import TextNowStorage
from .phone_utils import format_phone_number

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_SCHEMA = vol.Schema(
    {
        vol.Required("phone"): str,
        vol.Required("message"): str,
        vol.Optional("contact_name"): str,
    }
)

SERVICE_CONTACT_SCHEMA = vol.Schema(
    {
        vol.Required("name"): str,
        vol.Required("phone"): str,
    }
)


async def async_send_message(
    hass: HomeAssistant,
    coordinator: TextNowDataUpdateCoordinator,
    data: dict[str, Any],
) -> None:
    """Send a message via TextNow."""
    # Your existing send message implementation
    # Uses coordinator.client to send
    phone = data["phone"]
    message = data["message"]
    _LOGGER.info("Sending message to %s: %s", phone, message)
    
    # Example - replace with your actual client.send_sms() call
    # await coordinator.client.send_sms(phone, message)


async def async_add_contact(
    hass: HomeAssistant, 
    call: ServiceCall
) -> None:
    """Add a new contact."""
    name = call.data["name"]
    phone = call.data["phone"]
    
    try:
        formatted_phone = format_phone_number(phone)
    except ValueError:
        _LOGGER.error("Invalid phone number: %s", phone)
        return
    
    # Find coordinator from entry_id (passed via service context or lookup)
    for entry_id, coordinator in hass.data[DOMAIN].items():
        storage = TextNowStorage(hass, entry_id)
        contact_id = f"contact_{name.lower().replace(' ', '_')}"
        
        # Ensure unique ID
        contacts = await storage.async_get_contacts()
        counter = 1
        original_id = contact_id
        while contact_id in contacts:
            contact_id = f"{original_id}_{counter}"
            counter += 1
        
        await storage.async_save_contact(contact_id, name, formatted_phone)
        
        hass.bus.async_fire(
            f"{DOMAIN}_contact_added",
            {
                "contact_id": contact_id,
                "name": name,
                "phone": formatted_phone,
            }
        )
        _LOGGER.info("Added contact %s (%s)", name, formatted_phone)
        break


async def async_delete_contact(
    hass: HomeAssistant,
    entry_id: str,
    call: ServiceCall
) -> None:
    """Delete a contact."""
    contact_id = call.data["contact_id"]
    
    storage = TextNowStorage(hass, entry_id)
    await storage.async_delete_contact(contact_id)
    
    hass.bus.async_fire(
        f"{DOMAIN}_contact_deleted",
        {"contact_id": contact_id}
    )
    _LOGGER.info("Deleted contact %s", contact_id)


async def async_edit_contact(
    hass: HomeAssistant,
    call: ServiceCall
) -> None:
    """Edit a contact."""
    contact_id = call.data["contact_id"]
    name = call.data["name"]
    phone = call.data["phone"]
    
    try:
        formatted_phone = format_phone_number(phone)
    except ValueError:
        _LOGGER.error("Invalid phone number: %s", phone)
        return
    
    # Find coordinator/entry and update
    for entry_id, coordinator in hass.data[DOMAIN].items():
        storage = TextNowStorage(hass, entry_id)
        await storage.async_save_contact(contact_id, name, formatted_phone)
        
        hass.bus.async_fire(
            f"{DOMAIN}_contact_updated",
            {
                "contact_id": contact_id,
                "name": name,
                "phone": formatted_phone,
            }
        )
        _LOGGER.info("Updated contact %s to %s (%s)", contact_id, name, formatted_phone)
        break
