"""Higher-level chatbot manager for prompt handling and reply formatting."""

from __future__ import annotations

from chatbot.chatbot_client import ChatBotClient


class ChatbotManager:
    """Extract prompts, call the chatbot client, and format replies."""

    BOT_PREFIX = "/bot:"

    def __init__(self) -> None:
        self.client = ChatBotClient()

    def is_bot_command(self, text: str) -> bool:
        """Return True when a message should be handled by the chatbot."""

        return text.strip().lower().startswith(self.BOT_PREFIX)

    def extract_prompt(self, text: str) -> str:
        """Return the text after the /bot: prefix."""

        stripped_text = text.strip()
        return stripped_text[len(self.BOT_PREFIX) :].strip()

    def chat(self, text: str) -> str:
        """Process a /bot: command and return a plain bot reply."""

        prompt = self.extract_prompt(text)
        return self.client.chat(prompt)
