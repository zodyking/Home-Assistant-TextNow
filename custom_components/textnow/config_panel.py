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
            
            if not name or not phone:
                return self.json({"error": "Name and phone are required"}, status_code=400)
            
            # Format phone number (handles +1 prefix, strips non-digits, validates 10 digits)
            try:
                formatted_phone = format_phone_number(phone)
            except ValueError as e:
                return self.json({"error": str(e)}, status_code=400)
            
            # Generate contact_id if not provided
            if not contact_id:
                contact_id = f"contact_{name.lower().replace(' ', '_')}"
                # Ensure unique contact_id
                contacts = await storage.async_get_contacts()
                counter = 1
                original_id = contact_id
                while contact_id in contacts:
                    contact_id = f"{original_id}_{counter}"
                    counter += 1
            
            await storage.async_save_contact(contact_id, name, formatted_phone)
            hass.bus.async_fire(
                f"{DOMAIN}_contact_added",
                {"contact_id": contact_id, "name": name, "phone": formatted_phone},
            )
            return self.json({"success": True, "contact_id": contact_id, "phone": formatted_phone})
        
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
            
            if not contact_id or not name or not phone:
                return self.json({"error": "contact_id, name, and phone are required"}, status_code=400)
            
            # Format phone number (handles +1 prefix, strips non-digits, validates 10 digits)
            try:
                formatted_phone = format_phone_number(phone)
            except ValueError as e:
                return self.json({"error": str(e)}, status_code=400)
            
            await storage.async_save_contact(contact_id, name, formatted_phone)
            return self.json({"success": True, "phone": formatted_phone})

        return self.json({"error": "Invalid action"}, status_code=400)


class TextNowPanelJSView(HomeAssistantView):
    """Serve the TextNow panel JavaScript."""

    url = "/api/textnow/panel.js"
    name = "api:textnow:panel.js"
    requires_auth = False  # JS files need to be accessible without auth

    async def get(self, request):
        """Serve the panel JavaScript file."""
        import os
        
        # Try to get panel JS file from www directory first (HACS)
        www_file = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "www", "community", "textnow", "textnow-panel.js"
        )
        
        # Fallback to panel directory
        panel_file = os.path.join(
            os.path.dirname(__file__), "panel", "panel.js"
        )
        
        js_file = www_file if os.path.exists(www_file) else panel_file
        
        if not os.path.exists(js_file):
            return self.json({"error": "Panel JS file not found"}, status_code=404)
        
        with open(js_file, "r", encoding="utf-8") as f:
            js_content = f.read()
        
        from aiohttp import web
        response = web.Response(text=js_content, content_type="application/javascript")
        response.headers["Cache-Control"] = "no-cache"
        return response


async def async_setup_config_panel(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the config panel."""
    hass.http.register_view(TextNowConfigPanelView)
    hass.http.register_view(TextNowPanelJSView)
    return True

