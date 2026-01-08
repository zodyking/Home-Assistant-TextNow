"""The TextNow integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import frontend
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import TextNowDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

PANEL_URL_PATH = "textnow"
PANEL_TITLE = "TextNow"
PANEL_ICON = "mdi:message-text"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TextNow from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = TextNowDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await async_setup_services(hass, coordinator, entry.entry_id)

    # Register WebSocket API
    from .websocket import async_setup as async_setup_websocket
    async_setup_websocket(hass)

    # Register sidebar panel
    _register_panel(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: TextNowDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

        # Remove panel if no more entries
        if not hass.data[DOMAIN]:
            _remove_panel(hass)

    return unload_ok


async def async_setup_services(
    hass: HomeAssistant, 
    coordinator: TextNowDataUpdateCoordinator,
    entry_id: str
) -> None:
    """Set up services for TextNow."""
    from .services import (
        async_send_message,
        SERVICE_SEND_SCHEMA,
        async_add_contact,
        SERVICE_CONTACT_SCHEMA,
        SERVICE_DELETE_CONTACT_SCHEMA,
        async_delete_contact,
        async_edit_contact,
    )

    async def send_message_service(call):
        """Handle send message service call."""
        await async_send_message(hass, coordinator, call.data)

    # Register existing send service
    hass.services.async_register(
        DOMAIN, "send", send_message_service, schema=SERVICE_SEND_SCHEMA
    )

    # Register new contact services - all schemas imported from services.py
    hass.services.async_register(
        DOMAIN, "add_contact", async_add_contact, schema=SERVICE_CONTACT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "delete_contact", 
        lambda call: async_delete_contact(hass, entry_id, call), 
        schema=SERVICE_DELETE_CONTACT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "edit_contact", async_edit_contact, schema=SERVICE_CONTACT_SCHEMA
    )


@callback
def _register_panel(hass: HomeAssistant) -> None:
    """Register the TextNow sidebar panel."""
    if any(
        panel["url_path"] == PANEL_URL_PATH
        for panel in hass.data
