"""The TextNow integration."""
from __future__ import annotations

import logging
import os
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage, device_registry as dr
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN
from .coordinator import TextNowDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Panel configuration
PANEL_URL = "/api/panel_custom/textnow"
PANEL_ICON = "mdi:message-text"
PANEL_TITLE = "TextNow"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TextNow from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        coordinator = TextNowDataUpdateCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to initialize TextNow coordinator: %s", err)
        raise

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register the TextNow device explicitly so device triggers work reliably
    try:
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"TextNow ({entry.title})",
            manufacturer="TextNow",
            model="SMS Integration",
        )
        _LOGGER.info("Registered TextNow device for entry %s", entry.entry_id)
    except Exception as err:
        _LOGGER.error("Failed to register TextNow device: %s", err)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    try:
        await async_setup_services(hass, coordinator)
    except Exception as err:
        _LOGGER.error("Failed to register TextNow services: %s", err)

    # Register WebSocket API
    try:
        from .websocket import async_setup as async_setup_websocket
        async_setup_websocket(hass)
    except Exception as err:
        _LOGGER.error("Failed to register TextNow WebSocket API: %s", err)

    # Register sidebar panel (only once)
    try:
        await async_register_panel(hass)
    except Exception as err:
        _LOGGER.error("Failed to register TextNow panel: %s", err)

    return True


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the TextNow sidebar panel."""
    # Check if panel is already registered
    if DOMAIN in hass.data.get("frontend_panels", {}):
        return

    # Get the path to our panel JS file
    panel_path = os.path.join(os.path.dirname(__file__), "frontend")
    panel_url = f"/textnow_panel"

    # Register static path for the panel files
    await hass.http.async_register_static_paths([
        StaticPathConfig(panel_url, panel_path, cache_headers=False)
    ])

    # Register the custom panel
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="textnow-panel",
        frontend_url_path=DOMAIN,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{panel_url}/textnow-panel.js",
        embed_iframe=False,
        require_admin=False,
    )
    
    _LOGGER.info("TextNow panel registered")


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
        SERVICE_SEND_SCHEMA,
        SERVICE_SEND_MENU_SCHEMA,
    )

    async def send_message_service(call):
        """Handle send message service call."""
        await async_send_message(hass, coordinator, call.data)

    async def send_menu_service(call):
        """Handle send menu service call."""
        return await async_send_menu(hass, coordinator, call.data)

    # Register service with schema for validation
    hass.services.async_register(DOMAIN, "send", send_message_service, schema=SERVICE_SEND_SCHEMA)
    
    # Register send_menu service with response variable support
    hass.services.async_register(
        DOMAIN, 
        "send_menu", 
        send_menu_service, 
        schema=SERVICE_SEND_MENU_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

