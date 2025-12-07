"""Panel for TextNow contact management."""
from __future__ import annotations

import logging

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the TextNow panel."""
    # Register panel configuration
    hass.http.register_static_path(
        f"/textnow-panel",
        hass.config.path("custom_components/textnow/panel"),
        cache_headers=False,
    )

