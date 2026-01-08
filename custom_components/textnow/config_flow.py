"""Config flow for TextNow integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_POLLING_INTERVAL
from .storage import TextNowStorage
from .phone_utils import format_phone_number

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("connect_sid"): str,
        vol.Required("csrf"): str,
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

        errors: dict[str, str] = {}

        if not user_input.get("username"):
            errors["base"] = "username_required"
        elif not user_input.get("connect_sid"):
            errors["base"] = "connect_sid_required"
        elif not user_input.get("csrf"):
            errors["base"] = "csrf_required"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        return self.async_create_entry(
            title=user_input["username"],
            data={
                "username": user_input["username"],
                "connect_sid": user_input["connect_sid"],
                "csrf": user_input["csrf"],
                "polling_interval": DEFAULT_POLLING_INTERVAL,
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
        # Use a private attribute; no conflicting property
        self._config_entry = config_entry
        self.contact_id: str | None = None
        self.action_type: str | None = None

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the config entry."""
        return self._config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - show menu."""
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required("option"): vol.In(
                            {
                                "account": "Account Settings",
                                "contacts": "Manage Contacts",
                            }
                        ),
                    }
                ),
            )

        option = user_input.get("option")
        if option == "account":
            return await self.async_step_account()
        if option == "contacts":
            return await self.async_step_contacts()
        return await self.async_step_init()

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage account settings."""
        if user_input is not None:
            data = dict(self.config_entry.data)
            data.update(
                {
                    "username": user_input["username"],
                    "connect_sid": user_input["connect_sid"],
                    "csrf": user_input["csrf"],
                    "polling_interval": user_input.get(
                        "polling_interval", DEFAULT_POLLING_INTERVAL
                    ),
                }
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data
            )

            if "polling_interval" in user_input:
                domain_data = self.hass.data.get(DOMAIN, {})
                coordinator = domain_data.get(self.config_entry.entry_id)
                if coordinator is not None:
                    coordinator.update_interval = timedelta(
                        seconds=user_input["polling_interval"]
                    )

            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(
                    "username", default=self.config_entry.data.get("username", "")
                ): str,
                vol.Required(
                    "connect_sid",
                    default=self.config_entry.data.get("connect_sid", ""),
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
            }
        )

        return self.async_show_form(step_id="account", data_schema=schema)

    async def async_step_contacts(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage contacts - show menu."""
        if user_input is None:
            storage = TextNowStorage(self.hass, self.config_entry.entry_id)
            contacts = await storage.async_get_contacts()

            contact_list: list[str] = []
            if contacts:
                for contact_id, contact_data in contacts.items():
                    name = contact_data.get("name", "Unknown")
                    phone = contact_data.get("phone", "N/A")
                    contact_list.append(f"• {name} ({phone})")
                contacts_text = "\n".join(contact_list)
            else:
                contacts_text = "No contacts added yet."

            return self.async_show_form(
                step_id="contacts",
                data_schema=vol.Schema(
                    {
                        vol.Required("action"): vol.In(
                            {
                                "add": "Add New Contact",
                                "edit": "Edit Existing Contact",
                                "delete": "Delete Contact",
                                "back": "← Back to Main Menu",
                            }
                        ),
                    }
                ),
                description_placeholders={"contacts": contacts_text},
            )

        action = user_input.get("action")
        if action == "add":
            return await self.async_step_add_contact()
        if action == "edit":
            self.action_type = "edit"
            return await self.async_step_select_contact()
        if action == "delete":
            self.action_type = "delete"
            return await self.async_step_select_contact()
        if action == "back":
            return await self.async_step_init()
        return await self.async_step_contacts()

    async def async_step_select_contact(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a contact for edit or delete."""
        if not self.action_type:
            return await self.async_step_contacts()

        storage = TextNowStorage(self.hass, self.config_entry.entry_id)
        contacts = await storage.async_get_contacts()

        if not contacts:
            return self.async_abort(reason="no_contacts")

        if user_input is None:
            contact_options: dict[str, str] = {}
            for contact_id, contact_data in contacts.items():
                name = contact_data.get("name", "Unknown")
                phone = contact_data.get("phone", "N/A")
                contact_options[contact_id] = f"{name} ({phone})"

            return self.async_show_form(
                step_id="select_contact",
                data_schema=vol.Schema(
                    {
                        vol.Required("contact_id"): vol.In(contact_options),
                    }
                ),
                description_placeholders={
                    "action": self.action_type.capitalize()
                },
            )

        contact_id = user_input.get("contact_id")
        if not contact_id:
            return await self.async_step_contacts()

        self.contact_id = contact_id

        if self.action_type == "edit":
            return await self.async_step_edit_contact()
        if self.action_type == "delete":
            return await self.async_step_confirm_delete()
        return await self.async_step_contacts()

    async def async_step_confirm_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm contact deletion."""
        if not self.contact_id:
            return await self.async_step_contacts()

        storage = TextNowStorage(self.hass, self.config_entry.entry_id)
        contacts = await storage.async_get_contacts()

        if self.contact_id not in contacts:
            return self.async_a
