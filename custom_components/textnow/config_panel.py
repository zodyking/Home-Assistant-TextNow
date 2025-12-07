"""Config panel API for TextNow integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .storage import TextNowStorage
from .phone_utils import format_phone_number

_LOGGER = logging.getLogger(__name__)


class TextNowConfigPanelView(HomeAssistantView):
    """Handle config panel requests."""

    url = "/api/textnow/config"
    name = "api:textnow:config"
    requires_auth = True

    async def get(self, request):
        """Get config panel data."""
        hass = request.app["hass"]
        entry_id = request.query.get("entry_id")
        
        if not entry_id:
            return self.json({"error": "entry_id required"}, status_code=400)

        config_entry = hass.config_entries.async_get_entry(entry_id)
        if not config_entry:
            return self.json({"error": "Config entry not found"}, status_code=404)

        storage = TextNowStorage(hass, entry_id)
        contacts = await storage.async_get_contacts()

        return self.json({
            "entry_id": entry_id,
            "username": config_entry.data.get("username", ""),
            "polling_interval": config_entry.data.get("polling_interval", 30),
            "allowed_phones": config_entry.data.get("allowed_phones", []),
            "contacts": contacts,
        })

    async def post(self, request):
        """Update config panel data."""
        hass = request.app["hass"]
        data = await request.json()
        entry_id = data.get("entry_id")
        
        if not entry_id:
            return self.json({"error": "entry_id required"}, status_code=400)

        config_entry = hass.config_entries.async_get_entry(entry_id)
        if not config_entry:
            return self.json({"error": "Config entry not found"}, status_code=404)

        # Handle contact operations
        action = data.get("action")
        if action == "add_contact":
            storage = TextNowStorage(hass, entry_id)
            contact_id = data.get("contact_id")
            name = data.get("name")
            phone = data.get("phone")
            
            if contact_id and name and phone:
                try:
                    formatted_phone = format_phone_number(phone)
                    await storage.async_save_contact(contact_id, name, formatted_phone)
                    hass.bus.async_fire(
                        f"{DOMAIN}_contact_added",
                        {"contact_id": contact_id, "name": name, "phone": formatted_phone},
                    )
                    return self.json({"success": True})
                except ValueError as e:
                    return self.json({"error": str(e)}, status_code=400)
        
        elif action == "delete_contact":
            storage = TextNowStorage(hass, entry_id)
            contact_id = data.get("contact_id")
            
            if contact_id:
                await storage.async_delete_contact(contact_id)
                hass.bus.async_fire(
                    f"{DOMAIN}_contact_deleted",
                    {"contact_id": contact_id},
                )
                return self.json({"success": True})
        
        elif action == "update_contact":
            storage = TextNowStorage(hass, entry_id)
            contact_id = data.get("contact_id")
            name = data.get("name")
            phone = data.get("phone")
            
            if contact_id and name and phone:
                try:
                    formatted_phone = format_phone_number(phone)
                    await storage.async_save_contact(contact_id, name, formatted_phone)
                    return self.json({"success": True})
                except ValueError as e:
                    return self.json({"error": str(e)}, status_code=400)

        return self.json({"error": "Invalid action"}, status_code=400)


class TextNowPanelView(HomeAssistantView):
    """Serve the TextNow panel HTML."""

    url = "/api/textnow/panel"
    name = "api:textnow:panel"
    requires_auth = True

    async def get(self, request):
        """Serve the panel HTML."""
        import os
        
        # Get panel HTML file path
        panel_file = os.path.join(
            os.path.dirname(__file__), "panel", "panel.html"
        )
        
        if not os.path.exists(panel_file):
            return self.json({"error": "Panel file not found"}, status_code=404)
        
        with open(panel_file, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        from aiohttp import web
        return web.Response(text=html_content, content_type="text/html")


async def async_setup_config_panel(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the config panel."""
    hass.http.register_view(TextNowConfigPanelView)
    hass.http.register_view(TextNowPanelView)
    return True

