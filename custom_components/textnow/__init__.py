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

    # Register panel (after successful setup)
    from .panel import async_register_panel
    await async_register_panel(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
        
        # Unregister panel if this was the last entry
        if not hass.data[DOMAIN]:
            from .panel import async_unregister_panel
            await async_unregister_panel(hass)

    return unload_ok


async def async_setup_services(hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator) -> None:
    """Set up services for TextNow."""
    from .services import (
        async_clear_pending,
        async_send_message,
        async_set_context,
        async_prompt_message,
        async_wait_for_reply,
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

    async def wait_for_reply_service(call):
        """Handle wait for reply service call."""
        result = await async_wait_for_reply(hass, coordinator, call.data)
        if result:
            _LOGGER.info("Wait for reply setup: %s", result)

    hass.services.async_register(DOMAIN, "send", send_message_service)
    hass.services.async_register(DOMAIN, "prompt", prompt_message_service)
    hass.services.async_register(DOMAIN, "clear_pending", clear_pending_service)
    hass.services.async_register(DOMAIN, "set_context", set_context_service)
    hass.services.async_register(DOMAIN, "wait_for_reply", wait_for_reply_service)

