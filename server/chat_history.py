"""Simple in-memory chat history storage.

This module exists so future summary, keyword, and moderation features
have one safe place to read chat history from.
"""

from __future__ import annotations


class ChatHistory:
    """Store protocol messages in insertion order."""

    def __init__(self) -> None:
        self._messages: list[dict[str, object]] = []

    def add_message(self, message: dict[str, object]) -> None:
        """Save one validated protocol message."""

        self._messages.append(message)

    def get_messages(self) -> list[dict[str, object]]:
        """Return a copy so callers do not modify internal state."""

        return self._messages[:]

    def clear(self) -> None:
        """Remove all stored messages."""

        self._messages.clear()
