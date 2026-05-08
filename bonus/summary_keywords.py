"""Offline summary and keyword helpers for recent chat history."""

from __future__ import annotations

from collections import Counter
import re

SUMMARY_EMPTY_MESSAGE = "Not enough chat history to summarize yet."
KEYWORDS_EMPTY_MESSAGE = "No keywords available yet."
DEFAULT_HISTORY_LIMIT = 30

STOPWORDS = {
    "a", "about", "after", "all", "also", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "but", "by",
    "can", "could", "did", "do", "does", "doing", "for", "from", "had",
    "has", "have", "he", "her", "here", "hers", "him", "his", "how", "i",
    "if", "in", "into", "is", "it", "its", "just", "like", "me", "more",
    "most", "my", "no", "not", "now", "of", "on", "or", "our", "ours",
    "please", "she", "so", "some", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "to", "too", "up",
    "us", "was", "we", "were", "what", "when", "where", "which", "who",
    "why", "will", "with", "would", "you", "your", "yours",
}
IGNORED_TOKENS = {"bot", "system", "summary", "keywords"}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _normalize_messages(
    messages: list[dict[str, object]],
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []

    for message in messages[-limit:]:
        if not isinstance(message, dict):
            continue

        msg_type = str(message.get("type", "")).strip()
        if msg_type not in {"chat", "bot_response"}:
            continue

        content = str(message.get("content", "")).strip()
        if not content:
            continue

        sender = str(message.get("sender", "")).strip() or "Unknown"
        normalized.append({"sender": sender, "content": content, "type": msg_type})

    return normalized


def _build_banned_tokens(messages: list[dict[str, str]]) -> set[str]:
    banned = set(STOPWORDS)
    banned.update(IGNORED_TOKENS)

    for message in messages:
        banned.update(_tokenize(message["sender"]))

    return banned


def _extract_informative_tokens(text: str, banned_tokens: set[str]) -> list[str]:
    tokens = _tokenize(text)
    return [
        token
        for token in tokens
        if len(token) >= 3
        and not token.startswith("/")
        and token not in banned_tokens
        and not token.isdigit()
    ]


def _history_text_to_messages(history_text: str) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []

    for raw_line in history_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        sender = "Unknown"
        content = stripped
        if ":" in stripped:
            prefix, suffix = stripped.split(":", 1)
            sender = prefix.strip() or "Unknown"
            content = suffix.strip()

        msg_type = "bot_response" if sender.lower() == "bot" else "chat"
        messages.append({"sender": sender, "content": content, "type": msg_type})

    return messages


def extract_keywords(messages: list[dict[str, object]], max_keywords: int = 5) -> list[str]:
    """Return the top keywords from recent chat history."""

    normalized = _normalize_messages(messages)
    if not normalized or max_keywords <= 0:
        return []

    banned_tokens = _build_banned_tokens(normalized)
    counts: Counter[str] = Counter()

    for message in normalized:
        counts.update(_extract_informative_tokens(message["content"], banned_tokens))

    if not counts:
        return []

    ranked_tokens = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _count in ranked_tokens[:max_keywords]]


def generate_summary(messages: list[dict[str, object]], max_items: int = 2) -> str:
    """Return a short summary built from the most informative recent messages."""

    normalized = _normalize_messages(messages)
    if not normalized or max_items <= 0:
        return SUMMARY_EMPTY_MESSAGE

    banned_tokens = _build_banned_tokens(normalized)
    token_counts: Counter[str] = Counter()
    scored_messages: list[tuple[int, int, str]] = []

    for message in normalized:
        token_counts.update(_extract_informative_tokens(message["content"], banned_tokens))

    if not token_counts:
        return SUMMARY_EMPTY_MESSAGE

    for index, message in enumerate(normalized):
        tokens = _extract_informative_tokens(message["content"], banned_tokens)
        if not tokens:
            continue

        unique_tokens = set(tokens)
        score = sum(token_counts[token] for token in unique_tokens)
        scored_messages.append((score, index, message["content"]))

    if not scored_messages:
        return SUMMARY_EMPTY_MESSAGE

    top_messages = sorted(scored_messages, key=lambda item: (-item[0], item[1]))[:max_items]
    ordered_contents = [
        content
        for _score, _index, content in sorted(top_messages, key=lambda item: item[1])
    ]
    return " ".join(ordered_contents)


def summarize_chat(history_text: str) -> str:
    """Backward-compatible wrapper for callers that pass formatted chat text."""

    return generate_summary(_history_text_to_messages(history_text))


def keywords_status(messages: list[dict[str, object]], max_keywords: int = 5) -> str:
    """Return a display-ready keyword string for the GUI/server."""

    keywords = extract_keywords(messages, max_keywords=max_keywords)
    if not keywords:
        return KEYWORDS_EMPTY_MESSAGE
    return ", ".join(keywords)


def summary_status(messages: list[dict[str, object]]) -> str:
    """Return a display-ready summary string for the GUI/server."""

    return generate_summary(messages)
