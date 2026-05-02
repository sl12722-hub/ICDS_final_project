"""Shared JSON message protocol for all socket communication.

Every socket message is a JSON dictionary with these fields:
    type: required message type string
    sender: name of the user or system component
    target: recipient name or "all"
    content: main text payload
    timestamp: server or client timestamp string
    extra: dictionary for feature-specific data

Messages are encoded as newline-delimited JSON so sockets can read
one complete message at a time with ``readline()``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

MESSAGE_TYPES = {
    "chat",
    "system",
    "bot_request",
    "bot_response",
    "game_create",
    "game_join",
    "game_start",
    "game_move",
    "game_state",
    "game_end",
    "summary_request",
    "summary_response",
    "keywords_request",
    "keywords_response",
    "sentiment_result",
    "error",
}

REQUIRED_FIELDS = ("type", "sender", "target", "content", "timestamp", "extra")


class ProtocolError(ValueError):
    """Raised when incoming message data is not valid protocol data."""


def create_message(
    msg_type: str,
    sender: str,
    content: str,
    target: str = "all",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one protocol message with a standard timestamp."""

    if msg_type not in MESSAGE_TYPES:
        raise ProtocolError(f"Unsupported message type: {msg_type}")

    if not sender:
        raise ProtocolError("Message sender cannot be empty.")

    if not isinstance(target, str) or not target:
        raise ProtocolError("Message target must be a non-empty string.")

    return {
        "type": msg_type,
        "sender": str(sender),
        "target": target,
        "content": "" if content is None else str(content),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "extra": extra if isinstance(extra, dict) else {},
    }


def encode_message(message: dict[str, Any]) -> bytes:
    """Convert one message dictionary into bytes ready for sendall()."""

    validated_message = _validate_message_dict(message)
    return (json.dumps(validated_message, ensure_ascii=True) + "\n").encode("utf-8")


def decode_message(raw_data: bytes | str) -> dict[str, Any]:
    """Convert raw socket data into one validated message dictionary."""

    if isinstance(raw_data, bytes):
        raw_text = raw_data.decode("utf-8")
    elif isinstance(raw_data, str):
        raw_text = raw_data
    else:
        raise ProtocolError("Raw data must be bytes or string.")

    raw_text = raw_text.strip()
    if not raw_text:
        raise ProtocolError("Received empty message data.")

    try:
        message = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ProtocolError(f"Invalid JSON data: {error.msg}") from error

    return _validate_message_dict(message)


def _validate_message_dict(message: Any) -> dict[str, Any]:
    """Check that a message matches the shared protocol shape."""

    if not isinstance(message, dict):
        raise ProtocolError("Message must be a dictionary.")

    missing_fields = [field for field in REQUIRED_FIELDS if field not in message]
    if missing_fields:
        raise ProtocolError(f"Message is missing fields: {', '.join(missing_fields)}")

    if not isinstance(message["type"], str) or not message["type"]:
        raise ProtocolError("Message type must be a non-empty string.")

    if not isinstance(message["sender"], str) or not message["sender"]:
        raise ProtocolError("Message sender must be a non-empty string.")

    if not isinstance(message["target"], str) or not message["target"]:
        raise ProtocolError("Message target must be a non-empty string.")

    if not isinstance(message["content"], str):
        raise ProtocolError("Message content must be a string.")

    if not isinstance(message["timestamp"], str) or not message["timestamp"]:
        raise ProtocolError("Message timestamp must be a non-empty string.")

    if not isinstance(message["extra"], dict):
        raise ProtocolError("Message extra field must be a dictionary.")

    return {
        "type": message["type"],
        "sender": message["sender"],
        "target": message["target"],
        "content": message["content"],
        "timestamp": message["timestamp"],
        "extra": message["extra"],
    }
