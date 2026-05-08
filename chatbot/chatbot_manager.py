"""Higher-level chatbot manager for prompt handling and reply formatting."""

from __future__ import annotations

from collections import deque

from chatbot.chatbot_client import ChatBotClient


class ChatbotManager:
    """Store chatbot context, personality, and prompt-building rules."""

    BOT_PREFIX = "@bot"
    PERSONALITY_PREFIX = "/personality"
    DEFAULT_PERSONALITY = "friendly"
    MAX_EXCHANGES = 6
    PERSONALITIES = {
        "friendly": {
            "label": "Friendly Tutor",
            "system_prompt": (
                "You are a friendly tutor. Be warm, encouraging, and simple. "
                "Use the recent conversation to remember personal details."
            ),
        },
        "funny": {
            "label": "Funny Friend",
            "system_prompt": (
                "You are a funny friend. Be playful and light, but still helpful. "
                "Use the recent conversation to remember personal details."
            ),
        },
        "serious": {
            "label": "Serious Assistant",
            "system_prompt": (
                "You are a serious assistant. Be clear, formal, and direct. "
                "Use the recent conversation to remember personal details."
            ),
        },
    }
    PERSONALITY_ALIASES = {
        "friendly": "friendly",
        "friendly tutor": "friendly",
        "tutor": "friendly",
        "funny": "funny",
        "funny friend": "funny",
        "friend": "funny",
        "serious": "serious",
        "serious assistant": "serious",
        "assistant": "serious",
    }

    def __init__(self) -> None:
        self.client = ChatBotClient()
        self.user_histories: dict[str, deque[dict[str, str]]] = {}
        self.user_personalities: dict[str, str] = {}

    def is_bot_command(self, text: str) -> bool:
        """Return True when a message should be handled by the chatbot."""

        return text.strip().lower().startswith(self.BOT_PREFIX)

    def is_personality_command(self, text: str) -> bool:
        """Return True when a message should change chatbot personality."""

        return text.strip().lower().startswith(self.PERSONALITY_PREFIX)

    def extract_prompt(self, text: str) -> str:
        """Return the text after the chatbot prefix."""

        stripped_text = text.strip()
        return stripped_text[len(self.BOT_PREFIX) :].strip()

    def normalize_user_key(self, user_key: str | None) -> str:
        """Use a stable per-user key for bot history and personality."""

        normalized = (user_key or "").strip()
        if normalized:
            return normalized
        return "local_user"

    def get_personality_labels(self) -> list[str]:
        """Return the personality labels shown in the GUI dropdown."""

        return [details["label"] for details in self.PERSONALITIES.values()]

    def personality_key_from_label(self, label: str) -> str:
        """Convert a dropdown label into an internal personality key."""

        for key, details in self.PERSONALITIES.items():
            if details["label"] == label:
                return key
        return self.DEFAULT_PERSONALITY

    def get_personality_key(self, user_key: str | None) -> str:
        """Return the current personality key for the given user."""

        normalized_user = self.normalize_user_key(user_key)
        return self.user_personalities.get(normalized_user, self.DEFAULT_PERSONALITY)

    def get_personality_label(self, user_key: str | None) -> str:
        """Return the current personality label for the given user."""

        key = self.get_personality_key(user_key)
        return self.PERSONALITIES[key]["label"]

    def build_system_prompt(self, user_key: str | None) -> str:
        """Build the system prompt that matches the selected personality."""

        personality_key = self.get_personality_key(user_key)
        return self.PERSONALITIES[personality_key]["system_prompt"]

    def set_personality(self, user_key: str | None, personality_key: str) -> str:
        """Store a personality choice for the given user."""

        if personality_key not in self.PERSONALITIES:
            raise ValueError("Unknown personality.")

        normalized_user = self.normalize_user_key(user_key)
        self.user_personalities[normalized_user] = personality_key
        return self.PERSONALITIES[personality_key]["label"]

    def extract_personality_choice(self, text: str) -> str:
        """Return the normalized personality key from a command string."""

        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            return ""

        requested_value = parts[1].strip().lower()
        return self.PERSONALITY_ALIASES.get(requested_value, "")

    def handle_personality_command(self, user_key: str | None, text: str) -> str:
        """Apply a /personality command and return a user-facing message."""

        personality_key = self.extract_personality_choice(text)
        if not personality_key:
            return (
                "Use /personality friendly, /personality funny, "
                "or /personality serious."
            )

        label = self.set_personality(user_key, personality_key)
        return f"Bot personality set to {label}."

    def get_history(self, user_key: str | None) -> deque[dict[str, str]]:
        """Return the bounded history deque for one user."""

        normalized_user = self.normalize_user_key(user_key)
        if normalized_user not in self.user_histories:
            self.user_histories[normalized_user] = deque(maxlen=self.MAX_EXCHANGES * 2)
        return self.user_histories[normalized_user]

    def chat(self, user_key: str | None, text: str) -> str:
        """Process an @bot command, using recent context for one user."""

        prompt = self.extract_prompt(text)
        if not prompt:
            return self.client.chat(prompt)

        history = self.get_history(user_key)
        response = self.client.chat(
            prompt,
            conversation=list(history),
            system_prompt=self.build_system_prompt(user_key),
        )
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": response})
        return response
