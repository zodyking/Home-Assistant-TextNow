"""Panel registration for TextNow integration."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from homeassistant.components.frontend import async_remove_panel
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_NAME = "textnow"
PANEL_JS_URL = "/textnow-panel.js"
PANEL_TITLE = "TextNow"
PANEL_ICON = "mdi:message-text"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the TextNow panel."""
    try:
        from homeassistant.components.frontend import async_register_built_in_panel
        from homeassistant.components.http import StaticPathConfig
        
        # Get the path to the frontend JS file
        frontend_dir = Path(__file__).parent / "frontend"
        js_file = frontend_dir / "textnow-panel.js"
        
        if not js_file.exists():
            _LOGGER.error("Panel JS file not found at %s", js_file)
            return
        
        # Register static path for the JS file
        # This serves the file at /textnow-panel.js
        # StaticPathConfig expects url_path without leading slash and path to the directory
        # The file will be served at /textnow-panel.js (matching the filename)
        hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path="textnow-panel.js",
                path=str(frontend_dir),  # Path to the directory containing the file
            )
        ])
        
        # Register the panel
        await async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            frontend_url_path=PANEL_NAME,
            require_admin=False,
            config={
                "_panel_custom": {
                    "name": "textnow-panel",
                    "js_url": PANEL_JS_URL,
                    "module_url": PANEL_JS_URL,
                    "embed_iframe": False,
                },
            },
        )
        
        _LOGGER.debug("TextNow panel registered successfully")
        
    except ImportError as e:
        _LOGGER.debug("Frontend component not available: %s", e)
    except Exception as e:
        _LOGGER.warning("Failed to register TextNow panel: %s", e, exc_info=True)


async def async_unregister_panel(hass: HomeAssistant) -> None:
    """Unregister the TextNow panel."""
    try:
        await async_remove_panel(hass, PANEL_NAME)
        _LOGGER.debug("TextNow panel unregistered")
    except Exception as e:
        _LOGGER.debug("Failed to unregister TextNow panel: %s", e)

