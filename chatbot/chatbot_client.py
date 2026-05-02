"""Client-side chatbot API wrapper.

This module keeps chatbot API configuration in one place.
If no API configuration exists, it returns a friendly fallback reply.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class ChatBotClient:
    """Small chatbot client with optional OpenAI-compatible API support."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    def chat(self, user_message: str) -> str:
        """Return a chatbot reply for the provided user message."""

        prompt = user_message.strip()
        if not prompt:
            return "Please type something after /bot: so I know what to answer."

        if not self.api_key:
            return "Bot is not configured yet, but your message was received."

        return self._request_openai_response(prompt)

    def _request_openai_response(self, prompt: str) -> str:
        """Call an OpenAI-compatible chat completions endpoint."""

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful chatbot for a first-year CS chat project. Reply clearly and briefly.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.7,
        }

        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Chatbot API returned HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"Could not reach chatbot API: {error.reason}") from error
        except TimeoutError as error:
            raise RuntimeError("Chatbot API request timed out.") from error
        except json.JSONDecodeError as error:
            raise RuntimeError("Chatbot API returned invalid JSON.") from error

        try:
            return response_data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Chatbot API response format was unexpected.") from error
