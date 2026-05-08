"""Sentiment helpers for optional GUI chat labeling."""

from __future__ import annotations

import re

try:
    from textblob import TextBlob
except ImportError:  # pragma: no cover - optional dependency
    TextBlob = None  # type: ignore[assignment]

POSITIVE_WORDS = {"good", "great", "happy", "love", "excellent", "excited"}
NEGATIVE_WORDS = {"bad", "sad", "angry", "hate", "terrible", "worried"}

POSITIVE_LABEL = "Positive 😊"
NEUTRAL_LABEL = "Neutral 😐"
NEGATIVE_LABEL = "Negative 😡"


def _analyze_with_wordlist(text: str) -> str:
    words = re.findall(r"[a-z']+", text.lower())
    positive_hits = sum(1 for word in words if word in POSITIVE_WORDS)
    negative_hits = sum(1 for word in words if word in NEGATIVE_WORDS)

    if positive_hits > negative_hits:
        return POSITIVE_LABEL
    if negative_hits > positive_hits:
        return NEGATIVE_LABEL
    return NEUTRAL_LABEL


def analyze_sentiment(text: str) -> str:
    """Classify text as Positive 😊, Neutral 😐, or Negative 😡."""
    cleaned = text.strip()
    if not cleaned:
        return NEUTRAL_LABEL

    if TextBlob is None:
        return _analyze_with_wordlist(cleaned)

    try:
        polarity = TextBlob(cleaned).sentiment.polarity
    except Exception:
        # TextBlob should never break chat flow; fallback keeps behavior stable.
        return _analyze_with_wordlist(cleaned)

    if polarity > 0.1:
        return POSITIVE_LABEL
    if polarity < -0.1:
        return NEGATIVE_LABEL
    return NEUTRAL_LABEL
