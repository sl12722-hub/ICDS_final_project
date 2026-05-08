"""Unit tests for lazy chatbot configuration loading."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from chatbot.chatbot_client import ChatBotClient
from chatbot.chatbot_manager import ChatbotManager


class ChatbotClientLazyConfigTests(unittest.TestCase):
    def test_client_can_initialize_without_openai_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            client = ChatBotClient()

        self.assertIsNone(client.api_key)
        self.assertIsNone(client.base_url)
        self.assertIsNone(client.model)

    def test_empty_prompt_does_not_require_openai_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            client = ChatBotClient()
            response = client.chat("")

        self.assertIn("@bot", response)

    def test_real_prompt_requires_openai_api_key_only_when_used(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            client = ChatBotClient()
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY is not set"):
                client.chat("@bot hello")

    def test_chatbot_manager_can_initialize_without_openai_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            manager = ChatbotManager()

        self.assertIsInstance(manager.client, ChatBotClient)


if __name__ == "__main__":
    unittest.main()
