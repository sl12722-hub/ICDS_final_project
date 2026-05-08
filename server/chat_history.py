"""Simple in-memory chat history storage.

This module exists so future summary, keyword, and moderation features
have one safe place to read chat history from.

Chat history is stored with automatic memory management using collections.deque
with a maximum length of 200 messages to prevent unbounded memory growth.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any


class ChatHistory:
    """Store chat messages in insertion order with automatic memory management.
    
    Uses a deque with maxlen=200 to automatically drop old messages and prevent
    unbounded memory growth. Messages are stored as dictionaries for compatibility
    with the existing protocol.
    """

    def __init__(self, max_messages: int = 200) -> None:
        """Initialize history with a maximum message count.
        
        Args:
            max_messages: Maximum number of messages to keep in memory (default 200).
                         Older messages are automatically dropped when limit is reached.
        """
        self._messages: deque[dict[str, object]] = deque(maxlen=max_messages)
        self.max_messages = max_messages

    def add_message(self, *args: Any, **kwargs: Any) -> None:
        """Save a message to history.
        
        Supports two calling conventions for backward compatibility:
        - Old style: add_message(message_dict) - full protocol message dictionary
        - New style: add_message(sender, content, msg_type="chat") - individual fields
        
        Args:
            *args: Either (message_dict,) or (sender, content, msg_type)
            **kwargs: msg_type="chat", timestamp=current_time (for new style)
        """
        
        # Handle old-style call: add_message(dict)
        if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
            message_dict = args[0]
            self._messages.append(message_dict)
            return
        
        # Handle new-style call: add_message(sender, content, msg_type="chat")
        if len(args) >= 2:
            sender = str(args[0])
            content = str(args[1])
            msg_type = str(args[2]) if len(args) > 2 else kwargs.get("msg_type", "chat")
            timestamp = kwargs.get("timestamp", datetime.now().isoformat())
            
            message_dict = {
                "sender": sender,
                "content": content,
                "type": msg_type,
                "timestamp": timestamp,
            }
            self._messages.append(message_dict)
            return
        
        # Handle new-style call with kwargs: add_message(sender="Alice", content="Hello")
        if "sender" in kwargs and "content" in kwargs:
            sender = str(kwargs["sender"])
            content = str(kwargs["content"])
            msg_type = str(kwargs.get("msg_type", "chat"))
            timestamp = kwargs.get("timestamp", datetime.now().isoformat())
            
            message_dict = {
                "sender": sender,
                "content": content,
                "type": msg_type,
                "timestamp": timestamp,
            }
            self._messages.append(message_dict)
            return
        
        raise TypeError("Invalid arguments to add_message(). Use add_message(dict) "
                       "or add_message(sender, content, msg_type='chat')")

    def get_messages(self) -> list[dict[str, object]]:
        """Return a copy of all stored messages so callers do not modify internal state."""
        return list(self._messages)

    def get_recent_messages(self, limit: int = 30) -> list[dict[str, object]]:
        """Return the N most recent message objects.
        
        Args:
            limit: Number of recent messages to return (default 30).
                   If there are fewer than limit messages, return all available.
        
        Returns:
            List of the most recent message dictionaries, up to limit entries.
        """
        if limit <= 0:
            return []
        
        all_messages = list(self._messages)
        if len(all_messages) <= limit:
            return all_messages
        
        return all_messages[-limit:]

    def get_recent_text(self, limit: int = 30) -> str:
        """Return recent messages formatted as a single string for LLM context.
        
        Format each message as "Sender: Content" on separate lines, useful for
        including in prompts for summary, keyword extraction, or chatbot responses.
        
        Args:
            limit: Number of recent messages to include (default 30).
        
        Returns:
            Multi-line string with one message per line, or empty string if no messages.
        """
        messages = self.get_recent_messages(limit)
        
        lines = []
        for msg in messages:
            msg_type = str(msg.get("type", "")).strip()
            content = str(msg.get("content", "")).strip()
            
            # Skip empty content
            if not content:
                continue
            
            sender = str(msg.get("sender", "")).strip() or "Unknown"
            
            # Format based on message type
            if msg_type == "bot_response":
                lines.append(f"Bot: {content}")
            else:
                lines.append(f"{sender}: {content}")
        
        return "\n".join(lines)

    def clear(self) -> None:
        """Remove all stored messages."""
        self._messages.clear()
