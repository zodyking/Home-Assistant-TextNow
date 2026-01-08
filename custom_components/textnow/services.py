"""TextNow services."""
import logging
import voluptuous as vol
from typing import Any
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import TextNowDataUpdateCoordinator
from .storage import TextNowStorage
from .phone_utils import format_phone_number

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_SCHEMA = vol.Schema(
    {
        vol.Required("phone"): cv.string,
        vol.Required("message"): cv.string,
        vol.Optional("contact_name"): cv.string,
    }
)

SERVICE_CONTACT_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("phone"): cv.string,
    }
)

SERVICE_DELETE_CONTACT_SCHEMA = vol.Schema(
    {
        vol.Required("contact_id"): cv.string,
    }
)


async def async_send_message(
    hass: HomeAssistant,
    coordinator: TextNowDataUpdateCoordinator,
    data: dict[str, Any],
) -> None:
    """Send a message via TextNow."""
    phone = data["phone"]
    message = data["message"]
    
    # Your existing send message implementation using coordinator.client
    _LOGGER.info("Sending message to %s: %s", phone, message)
    # await coordinator.client.send_sms(phone, message)  # Uncomment your actual client call


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
    
    # Find matching entry/coordinator
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
    else:
        _LOGGER.warning("No TextNow coordinator found for add_contact")


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
    contact_id = call.data.get("contact_id")
    name = call.data["name"]
    phone = call.data["phone"]
    
    try:
        formatted_phone = format_phone_number(phone)
    except ValueError:
        _LOGGER.error("Invalid phone number: %s", phone)
        return
    
    # Find matching entry/coordinator
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
    else:
        _LOGGER.warning("No TextNow coordinator found for edit_contact")
