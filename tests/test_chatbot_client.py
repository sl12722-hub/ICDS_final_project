"""Unit tests for lazy chatbot configuration loading."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from chatbot.chatbot_client import ChatBotClient, ChatBotConfigurationError
from chatbot.chatbot_manager import ChatbotManager
from shared.ai_config import inspect_openai_config


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
            with self.assertRaisesRegex(ChatBotConfigurationError, "OPENAI_API_KEY is not set"):
                client.chat("@bot hello")

    def test_chatbot_manager_can_initialize_without_openai_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            manager = ChatbotManager()

        self.assertIsInstance(manager.client, ChatBotClient)

    def test_inspect_openai_config_reports_unconfigured_without_raising(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            status = inspect_openai_config()

        self.assertFalse(status.is_configured)
        self.assertFalse(status.has_api_key)
        self.assertEqual(status.base_url, "https://yinli.one/v1")
        self.assertEqual(status.model, "claude-sonnet-4-6")

    def test_inspect_openai_config_reports_resolved_values(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_BASE_URL": "https://example.com/custom",
                "OPENAI_MODEL": "demo-model",
            },
            clear=True,
        ):
            status = inspect_openai_config()

        self.assertTrue(status.is_configured)
        self.assertTrue(status.has_api_key)
        self.assertEqual(status.base_url, "https://example.com/custom/v1")
        self.assertEqual(status.model, "demo-model")


if __name__ == "__main__":
    unittest.main()
