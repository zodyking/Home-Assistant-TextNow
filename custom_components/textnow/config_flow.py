"""Config flow for TextNow integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, DEFAULT_POLLING_INTERVAL
from .storage import TextNowStorage

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("connect_sid"): str,
        vol.Required("csrf"): str,
        vol.Optional("polling_interval", default=DEFAULT_POLLING_INTERVAL): int,
        vol.Optional("allowed_phones", default=""): str,
    }
)


class TextNowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TextNow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        # Validate input
        if not user_input.get("username"):
            errors["base"] = "username_required"
        if not user_input.get("connect_sid"):
            errors["base"] = "connect_sid_required"
        if not user_input.get("csrf"):
            errors["base"] = "csrf_required"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        # Parse allowed phones
        allowed_phones = [
            p.strip()
            for p in user_input.get("allowed_phones", "").split(",")
            if p.strip()
        ]

        # Create entry
        return self.async_create_entry(
            title=user_input["username"],
            data={
                "username": user_input["username"],
                "connect_sid": user_input["connect_sid"],
                "csrf": user_input["csrf"],
                "polling_interval": user_input.get("polling_interval", DEFAULT_POLLING_INTERVAL),
                "allowed_phones": allowed_phones,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return TextNowOptionsFlowHandler(config_entry)


class TextNowOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for TextNow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({
                    vol.Required("option"): vol.In(["account", "contacts"]),
                }),
            )
        
        option = user_input.get("option")
        if option == "account":
            return await self.async_step_account()
        elif option == "contacts":
            return await self.async_step_contacts()
        
        return await self.async_step_init()

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage account settings."""
        if user_input is not None:
            # Parse allowed phones
            allowed_phones = [
                p.strip()
                for p in user_input.get("allowed_phones", "").split(",")
                if p.strip()
            ]
            user_input["allowed_phones"] = allowed_phones
            
            # Update config entry
            data = dict(self.config_entry.data)
            data.update(user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
            
            # Restart coordinator with new polling interval if changed
            if "polling_interval" in user_input:
                coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
                if coordinator:
                    coordinator.update_interval = timedelta(seconds=user_input["polling_interval"])
            
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(
                    "username", default=self.config_entry.data.get("username", "")
                ): str,
                vol.Required(
                    "connect_sid", default=self.config_entry.data.get("connect_sid", "")
                ): str,
                vol.Required(
                    "csrf", default=self.config_entry.data.get("csrf", "")
                ): str,
                vol.Optional(
                    "polling_interval",
                    default=self.config_entry.data.get(
                        "polling_interval", DEFAULT_POLLING_INTERVAL
                    ),
                ): int,
                vol.Optional(
                    "allowed_phones",
                    default=", ".join(
                        self.config_entry.data.get("allowed_phones", [])
                    ),
                ): str,
            }
        )

        return self.async_show_form(step_id="account", data_schema=schema)

    async def async_step_contacts(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage contacts."""
        storage = TextNowStorage(self.hass, self.config_entry.entry_id)
        contacts = await storage.async_get_contacts()

        if user_input is None:
            # Show list of contacts
            contact_list = []
            for contact_id, contact_data in contacts.items():
                contact_list.append(f"{contact_id}: {contact_data.get('name', 'Unknown')} ({contact_data.get('phone', 'N/A')})")

            return self.async_show_form(
                step_id="contacts",
                data_schema=vol.Schema({
                    vol.Optional("action"): vol.In(["add", "edit", "delete"]),
                    vol.Optional("contact_id"): vol.In(list(contacts.keys()) if contacts else []),
                }),
                description_placeholders={"contacts": "\n".join(contact_list) if contact_list else "No contacts"},
            )

        action = user_input.get("action")
        if action == "add":
            return await self.async_step_add_contact()
        elif action == "edit":
            contact_id = user_input.get("contact_id")
            if contact_id:
                return await self.async_step_edit_contact(contact_id)
        elif action == "delete":
            contact_id = user_input.get("contact_id")
            if contact_id and contact_id in contacts:
                await storage.async_delete_contact(contact_id)
                # Fire event to remove sensor
                self.hass.bus.async_fire(
                    f"{DOMAIN}_contact_deleted",
                    {"contact_id": contact_id},
                )
                return self.async_create_entry(title="", data={})

        return await self.async_step_contacts()

    async def async_step_add_contact(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new contact."""
        if user_input is None:
            return self.async_show_form(
                step_id="add_contact",
                data_schema=vol.Schema({
                    vol.Required("name"): str,
                    vol.Required("phone"): str,
                }),
            )

        storage = TextNowStorage(self.hass, self.config_entry.entry_id)
        contact_id = f"contact_{user_input['name'].lower().replace(' ', '_')}"
        
        # Ensure unique contact_id
        contacts = await storage.async_get_contacts()
        counter = 1
        original_id = contact_id
        while contact_id in contacts:
            contact_id = f"{original_id}_{counter}"
            counter += 1

        await storage.async_save_contact(
            contact_id, user_input["name"], user_input["phone"]
        )

        # Fire event to add sensor
        self.hass.bus.async_fire(
            f"{DOMAIN}_contact_added",
            {
                "contact_id": contact_id,
                "name": user_input["name"],
                "phone": user_input["phone"],
            },
        )

        return self.async_create_entry(title="", data={})

    async def async_step_edit_contact(
        self, contact_id: str, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit a contact."""
        storage = TextNowStorage(self.hass, self.config_entry.entry_id)
        contacts = await storage.async_get_contacts()

        if contact_id not in contacts:
            return self.async_abort(reason="contact_not_found")

        contact = contacts[contact_id]

        if user_input is None:
            return self.async_show_form(
                step_id="edit_contact",
                data_schema=vol.Schema({
                    vol.Required("name", default=contact.get("name", "")): str,
                    vol.Required("phone", default=contact.get("phone", "")): str,
                }),
            )

        await storage.async_save_contact(
            contact_id, user_input["name"], user_input["phone"]
        )

        return self.async_create_entry(title="", data={})

