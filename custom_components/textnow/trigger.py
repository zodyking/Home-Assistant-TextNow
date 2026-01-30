"""Trigger platform for TextNow integration."""
from __future__ import annotations

import logging
import re
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
TRIGGER_TYPE_PHRASE_RECEIVED = "phrase_received"

CONF_TYPE = "type"
CONF_CONTACT_ID = "contact_id"
CONF_PHONE = "phone"
CONF_PHRASE = "phrase"
CONF_MATCH_TYPE = "match_type"

# Match types for phrase matching
MATCH_TYPE_CONTAINS = "contains"
MATCH_TYPE_EXACT = "exact"
MATCH_TYPE_STARTS_WITH = "starts_with"
MATCH_TYPE_REGEX = "regex"

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(CONF_TYPE): vol.In([TRIGGER_TYPE_MESSAGE_RECEIVED, TRIGGER_TYPE_PHRASE_RECEIVED]),
        vol.Optional(CONF_CONTACT_ID): cv.string,
        vol.Optional(CONF_PHONE): cv.string,
        # For phrase_received trigger type
        vol.Optional(CONF_PHRASE): cv.string,
        vol.Optional(CONF_MATCH_TYPE, default=MATCH_TYPE_CONTAINS): vol.In([
            MATCH_TYPE_CONTAINS,
            MATCH_TYPE_EXACT,
            MATCH_TYPE_STARTS_WITH,
            MATCH_TYPE_REGEX,
        ]),
    }
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    return TRIGGER_SCHEMA(config)


def _match_phrase(text: str, phrase: str, match_type: str) -> bool:
    """Check if text matches phrase based on match type."""
    if not phrase:
        return True  # No phrase filter means match all
    
    text_lower = text.lower().strip()
    phrase_lower = phrase.lower().strip()
    
    if match_type == MATCH_TYPE_EXACT:
        return text_lower == phrase_lower
    elif match_type == MATCH_TYPE_STARTS_WITH:
        return text_lower.startswith(phrase_lower)
    elif match_type == MATCH_TYPE_REGEX:
        try:
            return bool(re.search(phrase, text, re.IGNORECASE))
        except re.error:
            _LOGGER.warning("Invalid regex pattern: %s", phrase)
            return False
    else:  # MATCH_TYPE_CONTAINS (default)
        return phrase_lower in text_lower


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
    phrase_filter = config.get(CONF_PHRASE)
    match_type = config.get(CONF_MATCH_TYPE, MATCH_TYPE_CONTAINS)

    job = HassJob(action, f"TextNow trigger {trigger_type}")

    @callback
    def handle_event(event: Event) -> None:
        """Handle the event."""
        event_data = event.data
        message_text = event_data.get(ATTR_TEXT, "")

        # Apply contact filter
        if contact_id_filter:
            # Handle both entity_id format and raw contact_id
            event_contact = event_data.get(ATTR_CONTACT_ID, "")
            filter_contact = contact_id_filter
            
            # Normalize: remove sensor.textnow_ prefix if present for comparison
            if filter_contact.startswith("sensor.textnow_"):
                filter_contact = filter_contact.replace("sensor.textnow_", "")
            
            if event_contact != filter_contact and event_contact != contact_id_filter:
                return

        # Apply phone filter
        if phone_filter:
            if event_data.get(ATTR_PHONE) != phone_filter:
                return

        # Apply phrase filter for phrase_received trigger type
        if trigger_type == TRIGGER_TYPE_PHRASE_RECEIVED:
            if not phrase_filter:
                _LOGGER.warning("phrase_received trigger requires a phrase to be set")
                return
            if not _match_phrase(message_text, phrase_filter, match_type):
                return

        # Build trigger data with variables for use in automations
        trigger_data = {
            **trigger_info["trigger_data"],
            "platform": DOMAIN,
            "type": trigger_type,
            # Core variables for automation templates
            "contact_name": event_data.get("contact_name", ""),
            "message": event_data.get(ATTR_TEXT, ""),
            # Additional context
            "phone": event_data.get(ATTR_PHONE),
            "contact_id": event_data.get(ATTR_CONTACT_ID),
            "text": event_data.get(ATTR_TEXT),
            "message_id": event_data.get("message_id"),
            "timestamp": event_data.get("timestamp"),
        }

        # Add matched phrase info for phrase_received
        if trigger_type == TRIGGER_TYPE_PHRASE_RECEIVED:
            trigger_data["matched_phrase"] = phrase_filter

        hass.async_run_hass_job(job, {"trigger": trigger_data})

    # Subscribe to event - both trigger types listen to the same event
    unsub = hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, handle_event)
    return unsub

