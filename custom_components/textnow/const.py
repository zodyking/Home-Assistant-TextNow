"""Constants for the TextNow integration."""
from typing import Final

DOMAIN: Final = "textnow"

# Event types
EVENT_MESSAGE_RECEIVED: Final = "textnow_message_received"
EVENT_REPLY_PARSED: Final = "textnow_reply_parsed"

# Storage keys
STORAGE_KEY: Final = f"{DOMAIN}.storage"
STORAGE_VERSION: Final = 1

# Defaults
DEFAULT_POLLING_INTERVAL: Final = 30  # seconds
DEFAULT_TTL_SECONDS: Final = 300  # 5 minutes

# Attributes
ATTR_PHONE: Final = "phone"
ATTR_LAST_INBOUND: Final = "last_inbound"
ATTR_LAST_INBOUND_TS: Final = "last_inbound_ts"
ATTR_LAST_OUTBOUND: Final = "last_outbound"
ATTR_LAST_OUTBOUND_TS: Final = "last_outbound_ts"
ATTR_PENDING: Final = "pending"
ATTR_CONTEXT: Final = "context"
ATTR_CONTACT_ID: Final = "contact_id"
ATTR_MESSAGE_ID: Final = "message_id"
ATTR_TIMESTAMP: Final = "timestamp"
ATTR_TEXT: Final = "text"
ATTR_KEY: Final = "key"
ATTR_TYPE: Final = "type"
ATTR_VALUE: Final = "value"
ATTR_RAW_TEXT: Final = "raw_text"
ATTR_OPTION_INDEX: Final = "option_index"

