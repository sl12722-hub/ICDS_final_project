"""Unit tests for offline summary and keyword extraction."""

from __future__ import annotations

import unittest

from bonus.summary_keywords import (
    KEYWORDS_EMPTY_MESSAGE,
    SUMMARY_EMPTY_MESSAGE,
    extract_keywords,
    generate_summary,
    keywords_status,
)


class SummaryKeywordsTests(unittest.TestCase):
    def test_empty_input_returns_empty_defaults(self) -> None:
        self.assertEqual(generate_summary([]), SUMMARY_EMPTY_MESSAGE)
        self.assertEqual(extract_keywords([]), [])
        self.assertEqual(keywords_status([]), KEYWORDS_EMPTY_MESSAGE)

    def test_repeated_topic_keyword_extraction(self) -> None:
        messages = [
            {"sender": "Alice", "content": "Python sockets make this chat project fun", "type": "chat"},
            {"sender": "Bob", "content": "Python server code and Python client code both use sockets", "type": "chat"},
            {"sender": "Cara", "content": "We should debug the socket protocol before the demo", "type": "chat"},
        ]

        keywords = extract_keywords(messages)

        self.assertIn("python", keywords)
        self.assertIn("sockets", keywords)

    def test_stopword_filtering(self) -> None:
        messages = [
            {"sender": "Alice", "content": "the the the and and the project server", "type": "chat"},
        ]

        keywords = extract_keywords(messages)

        self.assertNotIn("the", keywords)
        self.assertNotIn("and", keywords)
        self.assertEqual(keywords, ["project", "server"])

    def test_summary_preserves_chronological_order(self) -> None:
        messages = [
            {"sender": "Alice", "content": "The demo needs better screenshots for the final slides", "type": "chat"},
            {"sender": "Bob", "content": "Okay", "type": "chat"},
            {"sender": "Cara", "content": "The final slides also need clearer screenshots of the GUI", "type": "chat"},
        ]

        summary = generate_summary(messages)

        self.assertEqual(
            summary,
            "The demo needs better screenshots for the final slides "
            "The final slides also need clearer screenshots of the GUI",
        )

    def test_commands_and_usernames_do_not_surface_as_keywords(self) -> None:
        messages = [
            {"sender": "Alice", "content": "/summary please review the server changes", "type": "chat"},
            {"sender": "Bob", "content": "Alice and Bob finished the server changes for the GUI", "type": "chat"},
        ]

        keywords = extract_keywords(messages)

        self.assertNotIn("alice", keywords)
        self.assertNotIn("bob", keywords)
        self.assertNotIn("summary", keywords)
        self.assertIn("server", keywords)


if __name__ == "__main__":
    unittest.main()
