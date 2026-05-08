"""Shared configuration for OpenAI-compatible model access."""

from __future__ import annotations

import os

DEFAULT_OPENAI_BASE_URL = "https://yinli.one"
DEFAULT_OPENAI_MODEL = "claude-sonnet-4-6"


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
