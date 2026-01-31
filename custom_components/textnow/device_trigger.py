"""Device triggers for TextNow integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_MESSAGE_RECEIVED

_LOGGER = logging.getLogger(__name__)

# Trigger types
TRIGGER_TYPE_MESSAGE_RECEIVED = "message_received"
TRIGGER_TYPE_PHRASE_RECEIVED = "phrase_received"

TRIGGER_TYPES = {TRIGGER_TYPE_MESSAGE_RECEIVED, TRIGGER_TYPE_PHRASE_RECEIVED}

CONF_PHRASE = "phrase"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Optional(CONF_PHRASE): cv.string,
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """Return a list of triggers for TextNow devices."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    
    if not device:
        return []
    
    # Check if this is a TextNow device
    is_textnow_device = any(
        identifier[0] == DOMAIN for identifier in device.identifiers
    )
    
    if not is_textnow_device:
        return []

    # Return TWO triggers for the entire TextNow device (not per-contact)
    triggers = [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: TRIGGER_TYPE_MESSAGE_RECEIVED,
        },
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: TRIGGER_TYPE_PHRASE_RECEIVED,
        },
    ]

    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """Return the capabilities of a trigger."""
    trigger_type = config[CONF_TYPE]

    if trigger_type == TRIGGER_TYPE_PHRASE_RECEIVED:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(CONF_PHRASE): cv.string,
                }
            )
        }

    return {}


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    trigger_type = config[CONF_TYPE]
    phrase = config.get(CONF_PHRASE, "").lower().strip()
    
    job = HassJob(action, f"TextNow device trigger {trigger_type}")

    @callback
    def handle_event(event: Event) -> None:
        """Handle the textnow_message_received event."""
        event_data = event.data
        message_text = event_data.get("text", "").lower()
        
        _LOGGER.debug(
            "TextNow trigger received message: '%s' (looking for phrase: '%s')",
            message_text,
            phrase
        )
        
        # For phrase_received, check if phrase is in message
        if trigger_type == TRIGGER_TYPE_PHRASE_RECEIVED:
            if not phrase:
                _LOGGER.warning("Phrase trigger has no phrase configured")
                return
            if phrase not in message_text:
                _LOGGER.debug("Phrase '%s' not found in message, skipping", phrase)
                return
            _LOGGER.info("Phrase '%s' matched in message!", phrase)
        
        # Store last trigger contact for "reply_to_sender" feature
        contact_id = event_data.get("contact_id", "")
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["last_trigger_contact"] = {
            "contact_id": contact_id,
            "contact_name": event_data.get("contact_name", ""),
            "phone": event_data.get("phone", ""),
            "entity_id": f"sensor.textnow_{contact_id}" if contact_id else "",
        }
        _LOGGER.debug("Stored last trigger contact: %s", hass.data[DOMAIN]["last_trigger_contact"])
        
        # Build trigger payload with all useful data
        trigger_payload = {
            **trigger_info.get("trigger_data", {}),
            "platform": "device",
            "type": trigger_type,
            "domain": DOMAIN,
            # Event data for templates
            "event": event,
            # Direct access to common fields
            "contact_name": event_data.get("contact_name", ""),
            "contact_id": contact_id,
            "message": event_data.get("text", ""),
            "text": event_data.get("text", ""),
            "phone": event_data.get("phone", ""),
        }
        
        if trigger_type == TRIGGER_TYPE_PHRASE_RECEIVED:
            trigger_payload["matched_phrase"] = phrase
        
        hass.async_run_hass_job(job, {"trigger": trigger_payload})

    # Subscribe to the message received event
    unsub = hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, handle_event)
    
    _LOGGER.debug(
        "Attached TextNow %s trigger%s",
        trigger_type,
        f" for phrase '{phrase}'" if phrase else ""
    )
    
    return unsub

