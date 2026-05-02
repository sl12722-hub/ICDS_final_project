"""Client-side chatbot API wrapper.

This module keeps chatbot API configuration in one place.
If no API configuration exists, it returns a friendly fallback reply.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request


class ChatBotClient:
    """Small chatbot client with optional OpenAI-compatible API support."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    def chat(
        self,
        user_message: str,
        conversation: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Return a chatbot reply for the provided user message."""

        prompt = user_message.strip()
        if not prompt:
            return "Please type something after /bot: so I know what to answer."

        if not self.api_key:
            return self._fallback_response(prompt, conversation or [], system_prompt or "")

        return self._request_openai_response(prompt, conversation or [], system_prompt or "")

    def _request_openai_response(
        self,
        prompt: str,
        conversation: list[dict[str, str]],
        system_prompt: str,
    ) -> str:
        """Call an OpenAI-compatible chat completions endpoint."""

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

    def _fallback_response(
        self,
        prompt: str,
        conversation: list[dict[str, str]],
        system_prompt: str,
    ) -> str:
        """Return a simple local reply when no API key is configured."""

        known_name = self._find_known_name(conversation, prompt)
        prompt_lower = prompt.lower()

        if "what is my name" in prompt_lower or "do you know my name" in prompt_lower:
            if known_name:
                return self._style_name_reply(known_name, system_prompt)
            return self._style_unknown_name_reply(system_prompt)

        current_name = self._extract_name(prompt)
        if current_name:
            return self._style_greeting_reply(current_name, system_prompt)

        return self._style_general_reply(prompt, system_prompt)

    def _find_known_name(self, conversation: list[dict[str, str]], prompt: str) -> str:
        """Search recent user messages for a statement like 'My name is Ryan'."""

        current_name = self._extract_name(prompt)
        if current_name:
            return current_name

        for message in reversed(conversation):
            if message.get("role") != "user":
                continue
            name = self._extract_name(message.get("content", ""))
            if name:
                return name
        return ""

    def _extract_name(self, text: str) -> str:
        """Pull a simple name out of a sentence when possible."""

        match = re.search(r"\bmy name is\s+([A-Za-z][A-Za-z0-9_-]*)", text, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _style_greeting_reply(self, name: str, system_prompt: str) -> str:
        """Reply when the user introduces themselves."""

        tone = self._detect_tone(system_prompt)
        if tone == "funny":
            return f"Nice to meet you, {name}. I will try my best to be funny and helpful."
        if tone == "serious":
            return f"Understood. I will remember that your name is {name}."
        return f"Nice to meet you, {name}. I will remember your name."

    def _style_name_reply(self, name: str, system_prompt: str) -> str:
        """Reply when the user asks the bot to recall their name."""

        tone = self._detect_tone(system_prompt)
        if tone == "funny":
            return f"Of course. Your name is {name}, and that is still a strong choice."
        if tone == "serious":
            return f"Your name is {name}."
        return f"Your name is {name}. I remembered it from our recent chat."

    def _style_unknown_name_reply(self, system_prompt: str) -> str:
        """Reply when the bot does not yet know the user's name."""

        tone = self._detect_tone(system_prompt)
        if tone == "funny":
            return "I do not know your name yet, but I am ready for the big reveal."
        if tone == "serious":
            return "I do not know your name yet. Please tell me first."
        return "I do not know your name yet. Tell me with '/bot: My name is ...'."

    def _style_general_reply(self, prompt: str, system_prompt: str) -> str:
        """Reply to a general prompt in the selected tone."""

        tone = self._detect_tone(system_prompt)
        if tone == "funny":
            return f"I heard you say: {prompt}. I am not fully configured yet, but I am still on the case."
        if tone == "serious":
            return f"I received your message: {prompt}. The bot is using local fallback mode right now."
        return (
            f"I received your message: {prompt}. "
            "Bot is not configured yet, but I can still keep a short local memory."
        )

    def _detect_tone(self, system_prompt: str) -> str:
        """Map the system prompt text back to one of the supported tones."""

        prompt_lower = system_prompt.lower()
        if "funny" in prompt_lower:
            return "funny"
        if "serious" in prompt_lower or "formal" in prompt_lower:
            return "serious"
        return "friendly"
