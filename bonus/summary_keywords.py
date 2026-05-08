"""Summary and keyword helpers for recent chat history."""

from __future__ import annotations

from collections import Counter
import re
from typing import Iterable


_SUMMARY_EMPTY = "No recent chat history to summarize."
_KEYWORDS_EMPTY: list[str] = []
_MAX_KEYWORDS = 10
_MIN_KEYWORDS = 5

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "not",
    "of",
    "on",
    "or",
    "our",
    "she",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "will",
    "with",
    "you",
    "your",
    "about",
    "after",
    "before",
    "can",
    "do",
    "does",
    "doing",
    "done",
    "from",
    "got",
    "going",
    "like",
    "look",
    "need",
    "okay",
    "please",
    "should",
    "so",
    "than",
    "then",
    "want",
    "would",
}


def summarize_chat(history_text: str) -> str:
    """Summarize recent chat history in a short paragraph."""

    cleaned_history = history_text.strip()
    if not cleaned_history:
        return _SUMMARY_EMPTY

    llm_summary = _llm_summary(cleaned_history)
    if llm_summary:
        return llm_summary

    return _fallback_summary(cleaned_history)


def extract_keywords(history_text: str) -> list[str]:
    """Extract important keywords from recent chat history."""

    cleaned_history = history_text.strip()
    if not cleaned_history:
        return _KEYWORDS_EMPTY.copy()

    keyword_list = _extract_keywords_with_yake(cleaned_history)
    if keyword_list:
        return _normalize_keyword_list(keyword_list, cleaned_history)

    return _frequency_keywords(cleaned_history)


def _llm_summary(history_text: str) -> str:
    """Try a configured chatbot LLM before falling back to local logic."""

    try:
        from chatbot.chatbot_client import ChatBotClient
    except Exception:
        return ""

    prompt = (
        "Summarize the following recent chat history in 2 to 4 short sentences. "
        "Focus on the main topics, questions, and decisions. Do not invent details.\n\n"
        f"{history_text}"
    )

    try:
        client = ChatBotClient()
        response_text = client.chat(
            prompt,
            conversation=[],
            system_prompt="You summarize recent group chat history.",
        )
    except Exception:
        return ""

    response_text = response_text.strip()
    if not response_text:
        return ""

    if 2 <= _sentence_count(response_text) <= 4:
        return response_text

    return ""


def _fallback_summary(history_text: str) -> str:
    """Build a simple summary from message lines and extracted keywords."""

    messages = _parse_history_lines(history_text)
    if not messages:
        return _SUMMARY_EMPTY

    speakers = _extract_speakers(messages)
    keywords = extract_keywords(history_text)
    latest_speaker, latest_content = messages[-1]

    sentence_one = _build_participant_sentence(speakers, len(messages))
    sentence_two = _build_topic_sentence(keywords)
    sentence_three = _build_latest_sentence(latest_speaker, latest_content)

    sentences = [sentence for sentence in (sentence_one, sentence_two, sentence_three) if sentence]
    return " ".join(sentences)


def _build_participant_sentence(speakers: list[str], message_count: int) -> str:
    if speakers:
        speaker_text = _join_human_list(speakers[:4])
        if len(speakers) > 4:
            speaker_text = f"{speaker_text} and others"
        return f"Recent chat involved {speaker_text} across {message_count} recent messages."

    return f"Recent chat covered {message_count} recent messages."


def _build_topic_sentence(keywords: list[str]) -> str:
    if keywords:
        topic_text = _join_human_list(keywords[:3])
        return f"Main topics included {topic_text}."

    return "The discussion stayed broad and did not surface a strong recurring topic."


def _build_latest_sentence(latest_speaker: str, latest_content: str) -> str:
    snippet = _shorten_text(latest_content, 18)
    if latest_speaker:
        return f"The latest exchange came from {latest_speaker} and focused on {snippet}."
    return f"The latest exchange focused on {snippet}."


def _extract_keywords_with_yake(history_text: str) -> list[str]:
    try:
        import yake
    except Exception:
        return []

    try:
        extractor = yake.KeywordExtractor(lan="en", n=3, top=_MAX_KEYWORDS)
        results = extractor.extract_keywords(history_text)
    except Exception:
        return []

    keywords: list[str] = []
    for keyword, _score in results:
        cleaned_keyword = _clean_keyword(str(keyword))
        if cleaned_keyword:
            keywords.append(cleaned_keyword)
    return keywords


def _frequency_keywords(history_text: str) -> list[str]:
    tokens = _tokenize_words(history_text)
    if not tokens:
        return _KEYWORDS_EMPTY.copy()

    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}

    for index, token in enumerate(tokens):
        normalized = token.lower()
        if _is_stopword(normalized):
            continue
        if len(normalized) < 2 and not _contains_cjk(normalized):
            continue

        counts[normalized] += 1
        first_seen.setdefault(normalized, index)

    if not counts:
        return _KEYWORDS_EMPTY.copy()

    ordered_terms = sorted(counts.items(), key=lambda item: (-item[1], first_seen[item[0]]))
    keywords = [term for term, _count in ordered_terms[:_MAX_KEYWORDS]]

    if len(keywords) < _MIN_KEYWORDS:
        for token in tokens:
            normalized = token.lower()
            if _is_stopword(normalized):
                continue
            if normalized in keywords:
                continue
            keywords.append(normalized)
            if len(keywords) >= min(_MIN_KEYWORDS, _MAX_KEYWORDS):
                break

    return keywords[:_MAX_KEYWORDS]


def _normalize_keyword_list(keywords: Iterable[str], history_text: str) -> list[str]:
    normalized_keywords: list[str] = []
    seen: set[str] = set()

    for keyword in keywords:
        cleaned = _clean_keyword(keyword)
        if not cleaned:
            continue

        key = cleaned.lower()
        if key in seen:
            continue

        seen.add(key)
        normalized_keywords.append(cleaned)
        if len(normalized_keywords) >= _MAX_KEYWORDS:
            break

    if len(normalized_keywords) < _MIN_KEYWORDS:
        supplemental_keywords = _frequency_keywords(history_text)
        for keyword in supplemental_keywords:
            if keyword in normalized_keywords:
                continue
            normalized_keywords.append(keyword)
            if len(normalized_keywords) >= _MIN_KEYWORDS:
                break

    return normalized_keywords


def _clean_keyword(keyword: str) -> str:
    cleaned = re.sub(r"\s+", " ", keyword.strip())
    cleaned = cleaned.strip(".,;:!?()[]{}<>'\"`“”‘’")
    return cleaned


def _parse_history_lines(history_text: str) -> list[tuple[str, str]]:
    messages: list[tuple[str, str]] = []
    for line in history_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        speaker, content = _split_history_line(stripped)
        if content:
            messages.append((speaker, content))

    return messages


def _split_history_line(line: str) -> tuple[str, str]:
    if ":" not in line:
        return "", line.strip()

    speaker, content = line.split(":", 1)
    return speaker.strip(), content.strip()


def _extract_speakers(messages: list[tuple[str, str]]) -> list[str]:
    speakers: list[str] = []
    seen: set[str] = set()

    for speaker, _content in messages:
        cleaned = speaker.strip()
        if not cleaned:
            continue

        normalized = cleaned.lower()
        if normalized in seen:
            continue

        seen.add(normalized)
        speakers.append(cleaned)

    return speakers


def _tokenize_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*|[\u4e00-\u9fff]+", text)


def _sentence_count(text: str) -> int:
    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?。！？])\s+", text) if segment.strip()]
    return len(sentences)


def _shorten_text(text: str, max_words: int) -> str:
    words = text.split()
    if not words:
        return "the recent discussion"

    if len(words) <= max_words:
        return text.strip()

    return " ".join(words[:max_words]).rstrip(".,;:!?") + "..."


def _join_human_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _is_stopword(token: str) -> bool:
    if token in _STOPWORDS:
        return True

    if token.startswith("http"):
        return True

    return False
