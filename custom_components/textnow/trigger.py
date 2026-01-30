"""Trigger platform for TextNow integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_MESSAGE_RECEIVED, ATTR_PHONE, ATTR_CONTACT_ID, ATTR_TEXT

_LOGGER = logging.getLogger(__name__)

# Trigger types
TRIGGER_TYPE_MESSAGE_RECEIVED = "message_received"

CONF_TYPE = "type"
CONF_CONTACT_ID = "contact_id"
CONF_PHONE = "phone"

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(CONF_TYPE): vol.In([TRIGGER_TYPE_MESSAGE_RECEIVED]),
        vol.Optional(CONF_CONTACT_ID): cv.string,
        vol.Optional(CONF_PHONE): cv.string,
    }
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    return TRIGGER_SCHEMA(config)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    trigger_type = config[CONF_TYPE]
    contact_id_filter = config.get(CONF_CONTACT_ID)
    phone_filter = config.get(CONF_PHONE)

    job = HassJob(action, f"TextNow trigger {trigger_type}")

    @callback
    def handle_event(event: Event) -> None:
        """Handle the event."""
        event_data = event.data

        # Apply filters
        if contact_id_filter:
            # Handle both entity_id format and raw contact_id
            event_contact = event_data.get(ATTR_CONTACT_ID, "")
            filter_contact = contact_id_filter
            
            # Normalize: remove sensor.textnow_ prefix if present for comparison
            if filter_contact.startswith("sensor.textnow_"):
                filter_contact = filter_contact.replace("sensor.textnow_", "")
            
            if event_contact != filter_contact and event_contact != contact_id_filter:
                return

        if phone_filter:
            if event_data.get(ATTR_PHONE) != phone_filter:
                return

        # Build trigger data
        trigger_data = {
            **trigger_info["trigger_data"],
            "platform": DOMAIN,
            "type": trigger_type,
            "phone": event_data.get(ATTR_PHONE),
            "contact_id": event_data.get(ATTR_CONTACT_ID),
            "text": event_data.get(ATTR_TEXT),
            "message_id": event_data.get("message_id"),
            "timestamp": event_data.get("timestamp"),
        }

        hass.async_run_hass_job(job, {"trigger": trigger_data})

    # Subscribe to event
    if trigger_type == TRIGGER_TYPE_MESSAGE_RECEIVED:
        unsub = hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, handle_event)
    else:
        _LOGGER.error("Unknown trigger type: %s", trigger_type)
        return lambda: None

    return unsub

