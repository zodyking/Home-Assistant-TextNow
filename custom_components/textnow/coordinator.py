"""DataUpdateCoordinator for TextNow."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import unquote

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
        self._xsrf_token = entry.data.get("xsrf_token", "")
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

    def _get_csrf_header_value(self) -> str:
        """Get the correct CSRF token value for X-CSRF-Token header.
        
        Deterministic logic from API documentation (matching server.py):
        1. Use XSRF-TOKEN cookie value if present
        2. If _csrf starts with 's%3A', URL-decode it
        3. Otherwise, use raw _csrf value
        """
        # First priority: Use XSRF-TOKEN cookie value if available
        if self._xsrf_token:
            return self._xsrf_token
        # Fallback: If _csrf starts with 's%3A', it's URL-encoded and needs decoding
        if self._csrf.startswith('s%3A'):
            return unquote(self._csrf)
        # Otherwise use _csrf as-is
        return self._csrf

    async def _ensure_session(self) -> None:
        """Ensure aiohttp session is initialized."""
        if self.session is None or self.session.closed:
            csrf_header_value = self._get_csrf_header_value()
            cookies = {
                "connect.sid": self._connect_sid,
                "_csrf": self._csrf,
            }
            # Add XSRF-TOKEN cookie if available
            if self._xsrf_token:
                cookies["XSRF-TOKEN"] = self._xsrf_token
            
            self.session = aiohttp.ClientSession(
                cookies=cookies,
                headers={
                    "X-CSRF-Token": csrf_header_value,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": f"{self._base_url}/messaging",
                    "Origin": self._base_url,
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
                "start_message_id": "0",
                "direction": "future",
                "page_size": "0",
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
                # Get response value (option number for choice type)
                if parsed.get("option_index") is not None:
                    response_value = str(parsed.get("option_index") + 1)  # 1, 2, 3, etc.
                else:
                    response_value = str(parsed["value"])
                
                # Fire reply parsed event with response_variable name if specified
                event_data = {
                    ATTR_PHONE: phone,
                    ATTR_CONTACT_ID: contact_id,
                    ATTR_TYPE: parsed["type"],
                    ATTR_VALUE: parsed["value"],
                    ATTR_RAW_TEXT: parsed["raw_text"],
                    ATTR_OPTION_INDEX: parsed.get("option_index"),
                    "response_number": response_value,  # The option number (1, 2, 3, etc.)
                }
                
                # Include response_variable name in event if specified
                response_variable = pending_data.get("response_variable")
                if response_variable:
                    event_data["response_variable"] = response_variable
                
                self.hass.bus.async_fire(EVENT_REPLY_PARSED, event_data)

                # Always clear pending after first match (removed keep_pending feature)
                await self.storage.async_clear_pending(phone, key)
                
                # Only process first match (one pending per phone)
                break

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
        """Send an SMS message."""
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
            await self._update_contact_last_outbound_by_phone(phone)

        except aiohttp.ClientError as e:
            _LOGGER.error("HTTP error sending message: %s", e)
            raise

    async def send_mms(self, phone: str, message: str, media_file_path: str) -> None:
        """Send an MMS message with image/media attachment.
        
        Uses 3-step API process:
        1. GET upload URL from /api/v3/attachment_url?message_type=2
        2. PUT file to pre-signed URL
        3. POST to /api/v3/send_attachment with form data
        """
        await self._ensure_session()
        if self.session is None:
            raise Exception("Session not initialized")

        import os
        
        # Verify file exists
        if not os.path.exists(media_file_path):
            raise Exception(f"Media file not found: {media_file_path}")
        
        # Determine content type from file extension
        filename_lower = os.path.basename(media_file_path).lower()
        if filename_lower.endswith('.png'):
            content_type = 'image/png'
        elif filename_lower.endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'image/jpeg'  # default for images
        
        try:
            # Step 1: Get upload URL
            upload_url_response = await self.session.get(
                f"{self._base_url}/api/v3/attachment_url?message_type=2"
            )
            
            if upload_url_response.status != 200:
                error_text = await upload_url_response.text()
                _LOGGER.error(
                    "Failed to get upload URL: %s %s", upload_url_response.status, error_text
                )
                raise Exception(f"Failed to get upload URL: {upload_url_response.status}")
            
            upload_data = await upload_url_response.json()
            pre_signed_url = upload_data.get('result')
            
            if not pre_signed_url:
                _LOGGER.error("No upload URL in response: %s", upload_data)
                raise Exception("No upload URL in response")
            
            # Step 2: Upload file to pre-signed URL
            with open(media_file_path, "rb") as f:
                file_data = f.read()
            
            upload_response = await self.session.put(
                pre_signed_url,
                data=file_data,
                headers={'Content-Type': content_type}
            )
            
            if upload_response.status != 200:
                error_text = await upload_response.text()
                _LOGGER.error(
                    "Failed to upload file: %s %s", upload_response.status, error_text
                )
                raise Exception(f"Failed to upload file: {upload_response.status}")
            
            # Step 3: Send message with attachment
            from aiohttp import FormData
            send_data = FormData()
            send_data.add_field("contact_value", phone)
            send_data.add_field("contact_type", "2")
            send_data.add_field("attachment_url", pre_signed_url)
            send_data.add_field("message_type", "2")
            send_data.add_field("media_type", "images")
            send_data.add_field("message", message)
            
            send_response = await self.session.post(
                f"{self._base_url}/api/v3/send_attachment",
                data=send_data
            )
            
            if send_response.status != 200:
                error_text = await send_response.text()
                _LOGGER.error(
                    "Failed to send MMS: %s %s", send_response.status, error_text
                )
                raise Exception(f"Failed to send MMS: {send_response.status}")
            
            _LOGGER.debug("MMS sent successfully to %s", phone)
            await self._update_contact_last_outbound_by_phone(phone)

        except Exception as e:
            _LOGGER.error("Error sending MMS: %s", e)
            raise
    
    async def send_voice_message(self, phone: str, audio_file_path: str) -> None:
        """Send a voice message with audio file.
        
        Uses 3-step API process:
        1. GET upload URL from /api/v3/attachment_url?message_type=3
        2. PUT audio file to pre-signed URL
        3. POST to /api/v3/send_attachment with form data
        """
        await self._ensure_session()
        if self.session is None:
            raise Exception("Session not initialized")

        import os
        
        # Verify file exists
        if not os.path.exists(audio_file_path):
            raise Exception(f"Audio file not found: {audio_file_path}")
        
        try:
            # Step 1: Get upload URL for voice message (message_type=3)
            upload_url_response = await self.session.get(
                f"{self._base_url}/api/v3/attachment_url?message_type=3"
            )
            
            if upload_url_response.status != 200:
                error_text = await upload_url_response.text()
                _LOGGER.error(
                    "Failed to get upload URL: %s %s", upload_url_response.status, error_text
                )
                raise Exception(f"Failed to get upload URL: {upload_url_response.status}")
            
            upload_data = await upload_url_response.json()
            pre_signed_url = upload_data.get('result')
            
            if not pre_signed_url:
                _LOGGER.error("No upload URL in response: %s", upload_data)
                raise Exception("No upload URL in response")
            
            # Step 2: Upload audio file to pre-signed URL
            with open(audio_file_path, "rb") as f:
                file_data = f.read()
            
            upload_response = await self.session.put(
                pre_signed_url,
                data=file_data,
                headers={'Content-Type': 'audio/mpeg'}
            )
            
            if upload_response.status != 200:
                error_text = await upload_response.text()
                _LOGGER.error(
                    "Failed to upload audio file: %s %s", upload_response.status, error_text
                )
                raise Exception(f"Failed to upload audio file: {upload_response.status}")
            
            # Step 3: Send voice message
            from aiohttp import FormData
            send_data = FormData()
            send_data.add_field("contact_value", phone)
            send_data.add_field("contact_type", "2")
            send_data.add_field("attachment_url", pre_signed_url)
            send_data.add_field("message_type", "3")
            send_data.add_field("media_type", "audio")
            send_data.add_field("message", "")  # Always empty for voice messages
            
            send_response = await self.session.post(
                f"{self._base_url}/api/v3/send_attachment",
                data=send_data
            )
            
            if send_response.status != 200:
                error_text = await send_response.text()
                _LOGGER.error(
                    "Failed to send voice message: %s %s", send_response.status, error_text
                )
                raise Exception(f"Failed to send voice message: {send_response.status}")
            
            _LOGGER.debug("Voice message sent successfully to %s", phone)
            await self._update_contact_last_outbound_by_phone(phone)

        except Exception as e:
            _LOGGER.error("Error sending voice message: %s", e)
            raise

    async def _update_contact_last_outbound_by_phone(self, phone: str) -> None:
        """Update last outbound timestamp for contact by phone number."""
        contacts = await self.storage.async_get_contacts()
        contact_id = None
        for cid, contact in contacts.items():
            if contact["phone"] == phone:
                contact_id = cid
                break
        if contact_id:
            await self._update_contact_last_outbound(contact_id)

    async def _update_contact_last_outbound(self, contact_id: str) -> None:
        """Update last outbound timestamp for contact."""
        # This will be handled by the sensor entity
        pass

