"""Client-side chatbot API wrapper.

This module keeps chatbot API configuration in one place and always
routes chatbot requests to the configured OpenAI-compatible model server.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from shared.ai_config import (
    DEFAULT_OPENAI_MODEL,
    get_openai_api_key,
    get_openai_base_url,
    get_openai_model,
)


class ChatBotClient:
    """Small chatbot client for an OpenAI-compatible model endpoint."""

    DEFAULT_MODEL = DEFAULT_OPENAI_MODEL

    def __init__(self) -> None:
        # Load model configuration lazily so normal chat can start without
        # requiring chatbot credentials in the environment.
        self.api_key: str | None = None
        self.base_url: str | None = None
        self.model: str | None = None

    def chat(
        self,
        user_message: str,
        conversation: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Return a chatbot reply for the provided user message."""

        prompt = user_message.strip()
        if not prompt:
            return "Please type something after @bot so I know what to answer."

        return self._request_model_response(prompt, conversation or [], system_prompt or "")

    def _ensure_runtime_config(self) -> None:
        """Load API configuration only when the chatbot is actually used."""

        if self.api_key is None:
            self.api_key = get_openai_api_key()
        if self.base_url is None:
            self.base_url = get_openai_base_url()
        if self.model is None:
            self.model = get_openai_model()

    def _request_model_response(
        self,
        prompt: str,
        conversation: list[dict[str, str]],
        system_prompt: str,
    ) -> str:
        """Call the configured OpenAI-compatible chat completions endpoint."""

        self._ensure_runtime_config()

        messages = [
            {
                "role": "system",
                "content": (
                    system_prompt
                    or "You are a helpful chatbot for a first-year CS chat project. "
                    "Reply clearly and briefly."
                ),
            }
        ]
        messages.extend(conversation)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
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
