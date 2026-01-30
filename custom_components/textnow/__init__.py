"""The TextNow integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage

from .const import DOMAIN
from .coordinator import TextNowDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TextNow from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = TextNowDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await async_setup_services(hass, coordinator)

    # Register WebSocket API
    from .websocket import async_setup as async_setup_websocket
    async_setup_websocket(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok


async def async_setup_services(hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator) -> None:
    """Set up services for TextNow."""
    from homeassistant.core import SupportsResponse
    from .services import (
        async_send_message,
        async_send_menu,
        async_wait_response,
        SERVICE_SEND_SCHEMA,
        SERVICE_SEND_MENU_SCHEMA,
        SERVICE_WAIT_RESPONSE_SCHEMA,
    )

    async def send_message_service(call):
        """Handle send message service call."""
        await async_send_message(hass, coordinator, call.data)

    async def send_menu_service(call):
        """Handle send menu service call."""
        await async_send_menu(hass, coordinator, call.data)

    async def wait_response_service(call):
        """Handle wait response service call."""
        return await async_wait_response(hass, coordinator, call.data)

    # Register service with schema for validation
    hass.services.async_register(DOMAIN, "send", send_message_service, schema=SERVICE_SEND_SCHEMA)
    
    # Register send_menu service
    hass.services.async_register(
        DOMAIN, 
        "send_menu", 
        send_menu_service, 
        schema=SERVICE_SEND_MENU_SCHEMA
    )
    
    # Register wait_response service with response variable support
    hass.services.async_register(
        DOMAIN,
        "wait_response",
        wait_response_service,
        schema=SERVICE_WAIT_RESPONSE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

