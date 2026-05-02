"""Client-side chatbot helpers.

This file is intentionally small for Issue #2. It only defines a stable
module location so later chatbot code can be added without reorganizing
the project again.
"""

from __future__ import annotations

from server.protocol import create_message


def build_bot_request(sender: str, prompt: str) -> dict[str, object]:
    """Create a protocol message for future chatbot requests."""

    return create_message("bot_request", sender, prompt, target="chatbot")
