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
        vol.Required("cookie_string"): str,
    }
)


def parse_cookie_string(cookie_string: str) -> dict[str, str]:
    """Parse cookie string and return dict of cookies.
    
    Matches the logic from server.py:
    - Split by semicolons (or newlines converted to semicolons)
    - Find first = sign for key=value pairs
    - Remove quotes from values if present
    """
    cookies = {}
    if not cookie_string:
        return cookies
    
    parts = cookie_string.replace('\n', ';').split(';')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        eq_index = part.find('=')
        if eq_index > 0:
            key = part[:eq_index].strip()
            value = part[eq_index + 1:].strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            cookies[key] = value
    
    return cookies


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
        elif not user_input.get("cookie_string"):
            errors["base"] = "cookie_string_required"
        else:
            # Parse cookie string
            cookie_string = user_input["cookie_string"]
            cookies = parse_cookie_string(cookie_string)
            
            # Validate required cookies
            if "connect.sid" not in cookies:
                errors["base"] = "connect_sid_missing"
            elif "_csrf" not in cookies:
                errors["base"] = "csrf_missing"
            elif "XSRF-TOKEN" not in cookies:
                errors["base"] = "xsrf_token_missing"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        # Parse cookies (already validated above)
        cookies = parse_cookie_string(user_input["cookie_string"])
        
        return self.async_create_entry(
            title=user_input["username"],
            data={
                "username": user_input["username"],
                "connect_sid": cookies["connect.sid"],
                "csrf": cookies["_csrf"],
                "xsrf_token": cookies.get("XSRF-TOKEN", ""),
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
        """Manage the options - main menu."""
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
            # Parse cookie string
            cookie_string = user_input["cookie_string"]
            cookies = parse_cookie_string(cookie_string)
            
            # Validate required cookies
            errors: dict[str, str] = {}
            if "connect.sid" not in cookies:
                errors["base"] = "connect_sid_missing"
            elif "_csrf" not in cookies:
                errors["base"] = "csrf_missing"
            elif "XSRF-TOKEN" not in cookies:
                errors["base"] = "xsrf_token_missing"
            
            if errors:
                # Reconstruct cookie string from existing values for display
                existing_cookie_string = self._reconstruct_cookie_string()
                schema = vol.Schema(
                    {
                        vol.Required(
                            "username", default=user_input.get("username", "")
                        ): str,
                        vol.Required(
                            "cookie_string", default=existing_cookie_string
                        ): str,
                        vol.Optional(
                            "polling_interval",
                            default=user_input.get(
                                "polling_interval", DEFAULT_POLLING_INTERVAL
                            ),
                        ): int,
                    }
                )
                return self.async_show_form(step_id="account", data_schema=schema, errors=errors)
            
            data = dict(self.config_entry.data)
            data.update(
                {
                    "username": user_input["username"],
                    "connect_sid": cookies["connect.sid"],
                    "csrf": cookies["_csrf"],
                    "xsrf_token": cookies.get("XSRF-TOKEN", ""),
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

        # Reconstruct cookie string from existing values for display
        existing_cookie_string = self._reconstruct_cookie_string()
        
        schema = vol.Schema(
            {
                vol.Required(
                    "username", default=self.config_entry.data.get("username", "")
                ): str,
                vol.Required(
                    "cookie_string", default=existing_cookie_string
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
    
    def _reconstruct_cookie_string(self) -> str:
        """Reconstruct cookie string from stored values for display in edit form."""
        parts = []
        if self.config_entry.data.get("connect_sid"):
            parts.append(f"connect.sid={self.config_entry.data['connect_sid']}")
        if self.config_entry.data.get("csrf"):
            parts.append(f"_csrf={self.config_entry.data['csrf']}")
        if self.config_entry.data.get("xsrf_token"):
            parts.append(f"XSRF-TOKEN={self.config_entry.data['xsrf_token']}")
        return "; ".join(parts) if parts else ""

    async def async_step_contacts(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage contacts - menu."""
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

    async def async_step_add_contact(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new contact."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="add_contact",
                data_schema=vol.Schema(
                    {
                        vol.Required("name"): str,
                        vol.Required("phone"): str,
                    }
                ),
            )

        # Format and validate phone number
        try:
            formatted_phone = format_phone_number(user_input["phone"])
        except ValueError:
            errors["base"] = "invalid_phone"
            return self.async_show_form(
                step_id="add_contact",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "name", default=user_input.get("name", "")
                        ): str,
                        vol.Required(
                            "phone", default=user_input.get("phone", "")
                        ): str,
                    }
                ),
                errors=errors,
            )

        storage = TextNowStorage(self.hass, self.config_entry.entry_id)
        contact_id = (
            f"contact_{user_input['name'].lower().replace(' ', '_')}"
        )

        contacts = await storage.async_get_contacts()
        counter = 1
        original_id = contact_id
        while contact_id in contacts:
            contact_id = f"{original_id}_{counter}"
            counter += 1

        await storage.async_save_contact(
            contact_id, user_input["name"], formatted_phone
        )

        # Fire event to add sensor
        self.hass.bus.async_fire(
            f"{DOMAIN}_contact_added",
            {
                "contact_id": contact_id,
                "name": user_input["name"],
                "phone": formatted_phone,
            },
        )

        return self.async_create_entry(title="", data={})

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
            return self.async_abort(reason="contact_not_found")

        contact = contacts[self.contact_id]
        contact_name = contact.get("name", "Unknown")

        if user_input is None:
            return self.async_show_form(
                step_id="confirm_delete",
                data_schema=vol.Schema(
                    {
                        vol.Required("confirm"): bool,
                    }
                ),
                description_placeholders={"name": contact_name},
            )

        if user_input.get("confirm"):
            await storage.async_delete_contact(self.contact_id)
            self.hass.bus.async_fire(
                f"{DOMAIN}_contact_deleted",
                {"contact_id": self.contact_id},
            )
            return self.async_create_entry(title="", data={})

        return await self.async_step_contacts()

    async def async_step_edit_contact(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit a contact."""
        if not self.contact_id:
            return await self.async_step_contacts()

        storage = TextNowStorage(self.hass, self.config_entry.entry_id)
        contacts = await storage.async_get_contacts()

        if self.contact_id not in contacts:
            return self.async_abort(reason="contact_not_found")

        contact = contacts[self.contact_id]
        errors: dict[str, str] = {}

        if user_input is None:
            display_phone = contact.get("phone", "").replace("+1", "")
            return self.async_show_form(
                step_id="edit_contact",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "name", default=contact.get("name", "")
                        ): str,
                        vol.Required("phone", default=display_phone): str,
                    }
                ),
            )

        try:
            formatted_phone = format_phone_number(user_input["phone"])
        except ValueError:
            errors["base"] = "invalid_phone"
            display_phone = user_input.get("phone", "").replace("+1", "")
            return self.async_show_form(
                step_id="edit_contact",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "name", default=user_input.get("name", "")
                        ): str,
                        vol.Required("phone", default=display_phone): str,
                    }
                ),
                errors=errors,
            )

        await storage.async_save_contact(
            self.contact_id, user_input["name"], formatted_phone
        )

        return self.async_create_entry(title="", data={})
