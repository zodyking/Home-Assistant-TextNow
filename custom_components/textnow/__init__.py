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

    # Register config panel API
    from .config_panel import async_setup_config_panel
    await async_setup_config_panel(hass, {})

    # Register side menu panel (optional - may fail if frontend not loaded)
    try:
        await async_register_panel(hass)
    except Exception as e:
        _LOGGER.warning("Failed to register TextNow panel: %s", e)

    return True


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the TextNow panel in the side menu."""
    try:
        # Import frontend component directly (not via hass.components)
        from homeassistant.components.frontend import async_register_built_in_panel
        
        # Register panel using panel_custom - serve JS through API endpoint
        # This works regardless of HACS installation method
        result = await async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="TextNow",
            sidebar_icon="mdi:message-text",
            frontend_url_path="textnow",
            require_admin=False,
            config={
                "_panel_custom": {
                    "name": "textnow-panel",
                    "embed_iframe": False,
                    "trust_external": False,
                    "js_url": "/api/textnow/panel.js",
                },
            },
        )
        
        if result is None:
            _LOGGER.debug("Panel registration returned None (may already be registered)")
        else:
            _LOGGER.debug("Panel registered successfully")
            
    except ImportError as e:
        # Frontend component not available
        _LOGGER.debug("Frontend component not available, skipping panel registration: %s", e)
        return
    except Exception as e:
        # Catch all other errors
        _LOGGER.warning("Panel registration failed: %s", e, exc_info=True)
        return


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok


async def async_setup_services(hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator) -> None:
    """Set up services for TextNow."""
    from .services import (
        async_clear_pending,
        async_send_message,
        async_set_context,
        async_prompt_message,
    )

    async def send_message_service(call):
        """Handle send message service call."""
        await async_send_message(hass, coordinator, call.data)

    async def prompt_message_service(call):
        """Handle prompt message service call."""
        await async_prompt_message(hass, coordinator, call.data)

    async def clear_pending_service(call):
        """Handle clear pending service call."""
        await async_clear_pending(hass, coordinator, call.data)

    async def set_context_service(call):
        """Handle set context service call."""
        await async_set_context(hass, coordinator, call.data)

    hass.services.async_register(DOMAIN, "send", send_message_service)
    hass.services.async_register(DOMAIN, "prompt", prompt_message_service)
    hass.services.async_register(DOMAIN, "clear_pending", clear_pending_service)
    hass.services.async_register(DOMAIN, "set_context", set_context_service)

