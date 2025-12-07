"""Parsing helper for TextNow replies."""
from __future__ import annotations

import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)


def parse_reply(
    raw_text: str,
    prompt_type: str,
    options: list[str] | None = None,
    regex: str | None = None,
) -> dict[str, Any] | None:
    """Parse a reply based on prompt type and constraints.

    Returns dict with:
    - type: prompt_type
    - value: parsed value
    - raw_text: original text
    - option_index: index if choice type (None otherwise)
    """
    raw_text = raw_text.strip()

    if prompt_type == "choice":
        if not options:
            return None

        # Try to match by number (1, 2, 3, etc.)
        try:
            num = int(raw_text)
            if 1 <= num <= len(options):
                return {
                    "type": "choice",
                    "value": options[num - 1],
                    "raw_text": raw_text,
                    "option_index": num - 1,
                }
        except ValueError:
            pass

        # Try to match by text (case-insensitive)
        for idx, option in enumerate(options):
            if raw_text.lower() == option.lower():
                return {
                    "type": "choice",
                    "value": option,
                    "raw_text": raw_text,
                    "option_index": idx,
                }

        # Try partial match
        for idx, option in enumerate(options):
            if option.lower() in raw_text.lower() or raw_text.lower() in option.lower():
                return {
                    "type": "choice",
                    "value": option,
                    "raw_text": raw_text,
                    "option_index": idx,
                }

        return None

    elif prompt_type == "text":
        if regex:
            try:
                pattern = re.compile(regex)
                match = pattern.search(raw_text)
                if match:
                    return {
                        "type": "text",
                        "value": match.group(0),
                        "raw_text": raw_text,
                        "option_index": None,
                    }
                return None
            except re.error as e:
                _LOGGER.warning("Invalid regex pattern: %s", e)
                return None
        else:
            # Accept any non-empty text
            if raw_text:
                return {
                    "type": "text",
                    "value": raw_text,
                    "raw_text": raw_text,
                    "option_index": None,
                }
            return None

    elif prompt_type == "number":
        try:
            num = float(raw_text)
            return {
                "type": "number",
                "value": num,
                "raw_text": raw_text,
                "option_index": None,
            }
        except ValueError:
            return None

    elif prompt_type == "boolean":
        text_lower = raw_text.lower()
        if text_lower in ("yes", "y", "true", "1", "on"):
            return {
                "type": "boolean",
                "value": True,
                "raw_text": raw_text,
                "option_index": None,
            }
        elif text_lower in ("no", "n", "false", "0", "off"):
            return {
                "type": "boolean",
                "value": False,
                "raw_text": raw_text,
                "option_index": None,
            }
        return None

    # Unknown type - accept as text
    if raw_text:
        return {
            "type": prompt_type,
            "value": raw_text,
            "raw_text": raw_text,
            "option_index": None,
        }

    return None

