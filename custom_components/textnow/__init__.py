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
    await async_setup_services(hass, coordinator)

    # Register WebSocket API
    from .websocket import async_setup as async_setup_websocket

    async_setup_websocket(hass)

    # Register sidebar panel (iframe) if not already present
    _register_panel(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: TextNowDataUpdateCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        await coordinator.async_shutdown()

        # If no more entries for this domain, remove the panel
        if not hass.data[DOMAIN]:
            _remove_panel(hass)

    return unload_ok


async def async_setup_services(
    hass: HomeAssistant, coordinator: TextNowDataUpdateCoordinator
) -> None:
    """Set up services for TextNow."""
    from .services import (
        async_send_message,
        SERVICE_SEND_SCHEMA,
    )

    async def send_message_service(call):
        """Handle send message service call."""
        await async_send_message(hass, coordinator, call.data)

    hass.services.async_register(
        DOMAIN, "send", send_message_service, schema=SERVICE_SEND_SCHEMA
    )


@callback
def _register_panel(hass: HomeAssistant) -> None:
    """Register the TextNow sidebar panel."""
    # Avoid duplicate registration
    if any(
        panel["url_path"] == PANEL_URL_PATH
        for panel in hass.data.get("frontend_panels", {}).values()
    ):
        return

    # This uses the built-in iframe panel type and points to an internal route.
    # Adjust the URL if your frontend/WS UI is served elsewhere.
    frontend.async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL_PATH,
        config={
            # Example: point to an internal path you handle in your websocket/HTTP UI.
            # You can change this to any relative URL that serves your TextNow UI.
            "url": "/textnow-panel",
        },
        require_admin=True,
    )


@callback
def _remove_panel(hass: HomeAssistant) -> None:
    """Remove the TextNow sidebar panel."""
    try:
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
    except ValueError:
        # Panel was not registered or already removed
        _LOGGER.debug("TextNow panel %s not found when removing", PANEL_URL_PATH)
