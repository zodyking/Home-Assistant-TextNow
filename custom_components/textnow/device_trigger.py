"""Device triggers for TextNow integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
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
    entity_registry = er.async_get(hass)
    triggers = []

    # Find all entities for this device
    for entry in er.async_entries_for_device(entity_registry, device_id):
        if entry.domain != "sensor" or not entry.entity_id.startswith("sensor.textnow_"):
            continue

        # Add message_received trigger
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: TRIGGER_TYPE_MESSAGE_RECEIVED,
            }
        )

        # Add phrase_received trigger
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: TRIGGER_TYPE_PHRASE_RECEIVED,
            }
        )

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
    entity_id = config.get(CONF_ENTITY_ID, "")
    phrase = config.get(CONF_PHRASE, "")

    # Extract contact_id from entity_id (sensor.textnow_contact_xxx -> contact_xxx)
    contact_id = ""
    if entity_id.startswith("sensor.textnow_"):
        contact_id = entity_id.replace("sensor.textnow_", "")

    # Build event data filter
    event_data = {}
    if contact_id:
        event_data["contact_id"] = contact_id

    # Create event trigger config
    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: EVENT_MESSAGE_RECEIVED,
    }
    if event_data:
        event_config[event_trigger.CONF_EVENT_DATA] = event_data

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

