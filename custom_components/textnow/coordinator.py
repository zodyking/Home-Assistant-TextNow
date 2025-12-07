"""DataUpdateCoordinator for TextNow."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_MESSAGE_RECEIVED,
    EVENT_REPLY_PARSED,
    ATTR_PHONE,
    ATTR_TEXT,
    ATTR_MESSAGE_ID,
    ATTR_TIMESTAMP,
    ATTR_CONTACT_ID,
    ATTR_KEY,
    ATTR_TYPE,
    ATTR_VALUE,
    ATTR_RAW_TEXT,
    ATTR_OPTION_INDEX,
)
from .parsing import parse_reply
from .storage import TextNowStorage

_LOGGER = logging.getLogger(__name__)


class TextNowDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TextNow data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.storage = TextNowStorage(hass, entry.entry_id)
        self.session: aiohttp.ClientSession | None = None
        self._allowed_phones = entry.data.get("allowed_phones", [])
        self._username = entry.data.get("username", "")
        self._connect_sid = entry.data.get("connect_sid", "")
        self._csrf = entry.data.get("csrf", "")
        self._base_url = "https://www.textnow.com"

        polling_interval = entry.data.get("polling_interval", 30)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=polling_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from TextNow."""
        try:
            await self._ensure_session()
            await self._poll_unread_messages()
            await self._cleanup_expired_pending()
            return {}
        except Exception as err:
            raise UpdateFailed(f"Error communicating with TextNow: {err}") from err

    async def _ensure_session(self) -> None:
        """Ensure aiohttp session is initialized."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                cookies={
                    "connect.sid": self._connect_sid,
                    "_csrf": self._csrf,
                },
                headers={
                    "X-CSRF-Token": self._csrf,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

    async def async_shutdown(self) -> None:
        """Close the session on shutdown."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _poll_unread_messages(self) -> None:
        """Poll for unread messages."""
        if self.session is None:
            return

        try:
            # GET /api/users/{username}/messages
            # Parameters: start_message_id=0&direction=future&page_size=0
            url = f"{self._base_url}/api/users/{self._username}/messages"
            params = {
                "start_message_id": 0,
                "direction": "future",
                "page_size": 0,
            }

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to fetch messages: %s %s", response.status, await response.text()
                    )
                    return

                data = await response.json()
                # API returns messages in a list or nested structure
                # Handle different possible response formats
                if isinstance(data, list):
                    messages = data
                elif isinstance(data, dict):
                    # Try common response wrapper keys
                    messages = (
                        data.get("messages", [])
                        or data.get("data", [])
                        or data.get("result", [])
                        or []
                    )
                else:
                    messages = []

            contacts = await self.storage.async_get_contacts()
            phone_to_contact = {contact["phone"]: cid for cid, contact in contacts.items()}

            for message in messages:
                # Message structure: id, contact_value, message, message_direction (1=incoming, 2=outgoing)
                message_id = str(message.get("id", ""))
                if not message_id:
                    continue

                # Only process incoming messages (message_direction == 1)
                if message.get("message_direction") != 1:
                    continue

                # Check if already processed
                if await self.storage.async_is_message_processed(message_id):
                    continue

                phone = message.get("contact_value", "")
                if not phone:
                    continue

                # Security: check allowed phones
                if self._allowed_phones and phone not in self._allowed_phones:
                    _LOGGER.warning("Received message from unauthorized phone: %s", phone)
                    continue

                text = message.get("message", "")
                # Try to get timestamp from message, fallback to now
                timestamp = message.get("timestamp") or message.get("date") or dt_util.utcnow().isoformat()

                # Find contact_id
                contact_id = phone_to_contact.get(phone, phone)

                # Fire message received event
                self.hass.bus.async_fire(
                    EVENT_MESSAGE_RECEIVED,
                    {
                        ATTR_PHONE: phone,
                        ATTR_TEXT: text,
                        ATTR_MESSAGE_ID: message_id,
                        ATTR_TIMESTAMP: timestamp,
                        ATTR_CONTACT_ID: contact_id,
                    },
                )

                # Update last_inbound for contact
                await self._update_contact_last_inbound(contact_id, timestamp)

                # Check for pending expectations
                await self._check_pending_expectations(phone, text, contact_id)

                # Mark message as processed
                await self.storage.async_add_processed_message_id(message_id)

                # Note: TextNow API doesn't have a separate "mark read" endpoint
                # Messages are considered read after fetching

        except aiohttp.ClientError as e:
            _LOGGER.error("HTTP error polling messages: %s", e)
        except Exception as e:
            _LOGGER.error("Error polling messages: %s", e)


    async def _check_pending_expectations(
        self, phone: str, text: str, contact_id: str
    ) -> None:
        """Check if message matches any pending expectations."""
        pending = await self.storage.async_get_pending(phone)
        if not pending:
            return

        for key, pending_data in list(pending.items()):
            prompt_type = pending_data.get("type", "text")
            options = pending_data.get("options")
            regex = pending_data.get("regex")

            parsed = parse_reply(text, prompt_type, options, regex)
            if parsed:
                # Fire reply parsed event
                self.hass.bus.async_fire(
                    EVENT_REPLY_PARSED,
                    {
                        ATTR_PHONE: phone,
                        ATTR_CONTACT_ID: contact_id,
                        ATTR_KEY: key,
                        ATTR_TYPE: parsed["type"],
                        ATTR_VALUE: parsed["value"],
                        ATTR_RAW_TEXT: parsed["raw_text"],
                        ATTR_OPTION_INDEX: parsed.get("option_index"),
                    },
                )

                # Clear pending unless keep_pending is True
                if not pending_data.get("keep_pending", False):
                    await self.storage.async_clear_pending(phone, key)

    async def _update_contact_last_inbound(self, contact_id: str, timestamp: str) -> None:
        """Update last inbound timestamp for contact."""
        # This will be handled by the sensor entity
        pass

    async def _cleanup_expired_pending(self) -> None:
        """Clean up expired pending expectations."""
        data = await self.storage.async_load()
        pending = data.get("pending", {})
        now = dt_util.utcnow()

        for phone, phone_pending in list(pending.items()):
            for key, pending_data in list(phone_pending.items()):
                created_at = pending_data.get("created_at")
                ttl_seconds = pending_data.get("ttl_seconds", 300)

                if created_at:
                    try:
                        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        if now - created_dt > timedelta(seconds=ttl_seconds):
                            await self.storage.async_clear_pending(phone, key)
                            _LOGGER.debug("Cleared expired pending: %s/%s", phone, key)
                    except (ValueError, TypeError):
                        pass

    async def send_message(self, phone: str, message: str) -> None:
        """Send a message."""
        await self._ensure_session()
        if self.session is None:
            raise Exception("Session not initialized")

        # POST /api/users/{username}/messages
        # JSON: {"contact_value": "phone", "message_direction": 2, "contact_type": 2, "message": "text"}
        url = f"{self._base_url}/api/users/{self._username}/messages"
        payload = {
            "contact_value": phone,
            "message_direction": 2,  # 2 = outgoing
            "contact_type": 2,  # 2 = phone number
            "message": message,
        }

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error(
                        "Failed to send message: %s %s", response.status, error_text
                    )
                    raise Exception(f"Failed to send message: {response.status}")

                _LOGGER.debug("Message sent successfully to %s", phone)

            # Update last_outbound for contact
            contacts = await self.storage.async_get_contacts()
            contact_id = None
            for cid, contact in contacts.items():
                if contact["phone"] == phone:
                    contact_id = cid
                    break
            if contact_id:
                await self._update_contact_last_outbound(contact_id)

        except aiohttp.ClientError as e:
            _LOGGER.error("HTTP error sending message: %s", e)
            raise

    async def _update_contact_last_outbound(self, contact_id: str) -> None:
        """Update last outbound timestamp for contact."""
        # This will be handled by the sensor entity
        pass

