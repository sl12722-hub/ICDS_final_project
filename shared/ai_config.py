"""Shared configuration for OpenAI-compatible model access."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_OPENAI_BASE_URL = "https://yinli.one"
DEFAULT_OPENAI_MODEL = "claude-sonnet-4-6"


@dataclass(frozen=True)
class OpenAIConfigStatus:
    """Describe the current OpenAI-compatible runtime configuration."""

    has_api_key: bool
    base_url: str
    model: str

    @property
    def is_configured(self) -> bool:
        return self.has_api_key


def normalize_openai_base_url(base_url: str) -> str:
    """Normalize an OpenAI-compatible base URL to include the /v1 prefix."""

    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


def get_openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Configure a working API key in the environment."
        )
    return api_key


def get_openai_base_url() -> str:
    return normalize_openai_base_url(
        os.getenv("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL).strip()
    )


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()


def inspect_openai_config() -> OpenAIConfigStatus:
    """Return the resolved AI configuration without raising for missing credentials."""

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    return OpenAIConfigStatus(
        has_api_key=bool(api_key),
        base_url=get_openai_base_url(),
        model=get_openai_model(),
    )
