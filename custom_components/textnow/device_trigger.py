"""Device triggers for TextNow integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_MESSAGE_RECEIVED

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
    phrase = config.get(CONF_PHRASE, "")

    # Create event trigger config - listen to ALL messages (no contact filter)
    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: EVENT_MESSAGE_RECEIVED,
    }

    # Wrap the action to filter by phrase if needed
    if trigger_type == TRIGGER_TYPE_PHRASE_RECEIVED and phrase:
        original_action = action

        async def phrase_filtered_action(run_variables, context=None):
            """Filter action by phrase match."""
            trigger_data = run_variables.get("trigger", {})
            event = trigger_data.get("event")
            if event:
                message_text = event.data.get("text", "").lower()
                if phrase.lower() not in message_text:
                    return  # Don't trigger if phrase not found
            await original_action(run_variables, context)

        action = phrase_filtered_action

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )

