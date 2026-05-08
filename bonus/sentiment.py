"""Offline sentiment helpers for GUI chat labeling."""

from __future__ import annotations

from dataclasses import dataclass
import re

try:
    from textblob import TextBlob
except ImportError:  # pragma: no cover - optional dependency
    TextBlob = None  # type: ignore[assignment]

POSITIVE_WORDS = {
    "amazing", "awesome", "beautiful", "brilliant", "cool", "delightful",
    "excellent", "excited", "fantastic", "glad", "good", "great", "happy",
    "helpful", "hopeful", "love", "loved", "lovely", "nice", "perfect",
    "pleased", "positive", "relaxed", "sweet", "thanks", "thankful", "wonderful",
}
NEGATIVE_WORDS = {
    "angry", "annoyed", "anxious", "awful", "bad", "confused", "depressed",
    "disappointed", "frustrated", "furious", "hate", "horrible", "mad",
    "miserable", "negative", "nervous", "poor", "sad", "scared", "stress",
    "stressed", "terrible", "tired", "upset", "worried", "worse", "worst",
}
NEGATION_WORDS = {
    "aint", "aren't", "can't", "couldn't", "didn't", "doesn't", "dont", "don't",
    "hardly", "isn't", "never", "no", "not", "nothing", "wasn't", "weren't",
    "won't", "wouldn't",
}
INTENSIFIERS = {
    "extremely": 1.8,
    "really": 1.35,
    "so": 1.25,
    "super": 1.5,
    "too": 1.2,
    "totally": 1.45,
    "very": 1.4,
}
POSITIVE_EMOJIS = {"😀", "😄", "😊", "😍", "🥳", "❤️", "👍"}
NEGATIVE_EMOJIS = {"😞", "😡", "😢", "😭", "😠", "👎", "💔"}

POSITIVE_LABEL = "Positive 😊"
NEUTRAL_LABEL = "Neutral 😐"
NEGATIVE_LABEL = "Negative 😡"


@dataclass(frozen=True)
class SentimentResult:
    """Structured sentiment result for one message."""

    label: str
    score: float


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def _score_with_wordlist(text: str) -> float:
    tokens = _tokenize(text)
    score = 0.0

    for index, token in enumerate(tokens):
        base = 0.0
        if token in POSITIVE_WORDS:
            base = 1.0
        elif token in NEGATIVE_WORDS:
            base = -1.0

        if base == 0.0:
            continue

        previous = tokens[index - 1] if index > 0 else ""
        two_back = tokens[index - 2] if index > 1 else ""
        weight = INTENSIFIERS.get(previous, 1.0)

        if previous in NEGATION_WORDS or two_back in NEGATION_WORDS:
            base *= -1.0
            weight *= 1.1

        score += base * weight

    if "!" in text:
        score *= 1.1

    emoji_boost = sum(0.7 for emoji in POSITIVE_EMOJIS if emoji in text)
    emoji_boost -= sum(0.7 for emoji in NEGATIVE_EMOJIS if emoji in text)
    score += emoji_boost

    token_count = max(len(tokens), 1)
    return score / token_count


def _score_with_textblob(text: str) -> float | None:
    if TextBlob is None:
        return None

    try:
        return float(TextBlob(text).sentiment.polarity)
    except Exception:
        return None


def analyze_sentiment_result(text: str) -> SentimentResult:
    """Return a sentiment label and score for one message."""

    cleaned = text.strip()
    if not cleaned:
        return SentimentResult(NEUTRAL_LABEL, 0.0)

    lexical_score = _score_with_wordlist(cleaned)
    textblob_score = _score_with_textblob(cleaned)

    if textblob_score is None:
        final_score = lexical_score
    else:
        final_score = (textblob_score * 0.75) + (lexical_score * 0.25)

    if final_score >= 0.12:
        return SentimentResult(POSITIVE_LABEL, final_score)
    if final_score <= -0.12:
        return SentimentResult(NEGATIVE_LABEL, final_score)
    return SentimentResult(NEUTRAL_LABEL, final_score)


def analyze_sentiment(text: str) -> str:
    """Classify text as Positive 😊, Neutral 😐, or Negative 😡."""

    return analyze_sentiment_result(text).label
