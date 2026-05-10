"""Tests for logging and friendly error handling."""

from __future__ import annotations

import socket
import unittest
from unittest.mock import patch

from chatbot.chatbot_client import (
    ChatBotAuthenticationError,
    ChatBotConfigurationError,
    ChatBotConnectionError,
    ChatBotResponseError,
)
from client.gui_client import GUIChatClient
from server.protocol import create_message, decode_message, encode_message
from server.server import ChatServer, ClientConnection


class ErrorHandlingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ChatServer(host="127.0.0.1", port=0)
        self.resources: list[object] = []

    def tearDown(self) -> None:
        for resource in reversed(self.resources):
            try:
                resource.close()
            except Exception:
                pass
        try:
            self.server.server_socket.close()
        except OSError:
            pass

    def _add_client(self, name: str) -> tuple[socket.socket, object, socket.socket]:
        client_socket, server_socket = socket.socketpair()
        client_file = client_socket.makefile("r", encoding="utf-8")
        server_file = server_socket.makefile("r", encoding="utf-8")
        connection = ClientConnection(
            socket=server_socket,
            file_obj=server_file,
            address=("local", 0),
            name=name,
            has_announced_join=True,
        )
        self.server.clients[server_socket] = connection
        self.server.name_to_socket[name] = server_socket
        self.resources.extend([client_file, client_socket, server_file, server_socket])
        return client_socket, client_file, server_socket

    def _read_message(self, client_file: object) -> dict[str, object]:
        line = client_file.readline()
        self.assertTrue(line)
        return decode_message(line)

    def test_game_join_fake_room_returns_friendly_error(self) -> None:
        _alice_client, alice_file, alice_server = self._add_client("Alice")

        self.server.route_message(
            alice_server,
            create_message(
                "game_join",
                "Alice",
                "join missing-room",
                extra={"room_id": "missing-room"},
            ),
        )

        message = self._read_message(alice_file)
        self.assertEqual(message["type"], "error")
        self.assertEqual(message["content"], "Game room not found.")

    def test_invalid_game_move_logs_and_returns_friendly_error(self) -> None:
        _alice_client, alice_file, alice_server = self._add_client("Alice")
        _bob_client, bob_file, bob_server = self._add_client("Bob")

        with self.assertLogs("server.server", level="INFO") as create_logs:
            self.server.route_message(
                alice_server,
                create_message("game_create", "Alice", "create room"),
            )
        create_message_obj = self._read_message(alice_file)
        room_id = str(create_message_obj["extra"]["room_id"])
        self.assertIn("Game room created", "\n".join(create_logs.output))

        with self.assertLogs("server.server", level="INFO") as join_logs:
            self.server.route_message(
                bob_server,
                create_message(
                    "game_join",
                    "Bob",
                    f"join {room_id}",
                    extra={"room_id": room_id},
                ),
            )
        self._read_message(alice_file)
        self._read_message(bob_file)
        self.assertIn("Game joined", "\n".join(join_logs.output))

        self.server.route_message(
            alice_server,
            create_message(
                "game_move",
                "Alice",
                "move",
                extra={"room_id": room_id, "row": 0, "col": 0},
            ),
        )
        self._read_message(alice_file)
        self._read_message(bob_file)

        with self.assertLogs("server.server", level="WARNING") as move_logs:
            self.server.route_message(
                alice_server,
                create_message(
                    "game_move",
                    "Alice",
                    "move",
                    extra={"room_id": room_id, "row": 0, "col": 1},
                ),
            )

        error_message = self._read_message(alice_file)
        self.assertEqual(error_message["type"], "error")
        self.assertEqual(error_message["content"], "Invalid move. It is not your turn.")
        self.assertIn("Invalid game move", "\n".join(move_logs.output))

    def test_chatbot_missing_config_returns_friendly_system_message(self) -> None:
        _alice_client, alice_file, _alice_server = self._add_client("Alice")
        _bob_client, bob_file, _bob_server = self._add_client("Bob")

        with patch.object(
            self.server.chatbot_manager,
            "chat",
            side_effect=ChatBotConfigurationError("OPENAI_API_KEY is not set"),
        ):
            with self.assertLogs("server.server", level="WARNING") as logs:
                self.server._handle_group_bot_mention("Alice", "@bot help")

        alice_message = self._read_message(alice_file)
        bob_message = self._read_message(bob_file)
        self.assertEqual(alice_message["type"], "system")
        self.assertEqual(alice_message["content"], "Bot is not configured on the server.")
        self.assertEqual(bob_message["content"], "Bot is not configured on the server.")
        self.assertIn("Chatbot error while handling mention from Alice", "\n".join(logs.output))

    def test_chatbot_auth_failure_returns_friendly_system_message(self) -> None:
        _alice_client, alice_file, _alice_server = self._add_client("Alice")
        _bob_client, bob_file, _bob_server = self._add_client("Bob")

        with patch.object(
            self.server.chatbot_manager,
            "chat",
            side_effect=ChatBotAuthenticationError("Chatbot API returned HTTP 401"),
        ):
            with self.assertLogs("server.server", level="ERROR") as logs:
                self.server._handle_group_bot_mention("Alice", "@bot help")

        alice_message = self._read_message(alice_file)
        bob_message = self._read_message(bob_file)
        self.assertEqual(alice_message["content"], "Bot service authentication failed.")
        self.assertEqual(bob_message["content"], "Bot service authentication failed.")
        self.assertIn("configured=", "\n".join(logs.output))

    def test_chatbot_network_failure_returns_friendly_system_message(self) -> None:
        _alice_client, alice_file, _alice_server = self._add_client("Alice")
        _bob_client, bob_file, _bob_server = self._add_client("Bob")

        with patch.object(
            self.server.chatbot_manager,
            "chat",
            side_effect=ChatBotConnectionError("Could not reach chatbot API: timed out"),
        ):
            with self.assertLogs("server.server", level="ERROR") as logs:
                self.server._handle_group_bot_mention("Alice", "@bot help")

        alice_message = self._read_message(alice_file)
        bob_message = self._read_message(bob_file)
        self.assertEqual(alice_message["content"], "Bot service is unreachable right now.")
        self.assertEqual(bob_message["content"], "Bot service is unreachable right now.")
        self.assertIn("Chatbot error while handling mention from Alice", "\n".join(logs.output))

    def test_chatbot_invalid_response_returns_friendly_system_message(self) -> None:
        _alice_client, alice_file, _alice_server = self._add_client("Alice")
        _bob_client, bob_file, _bob_server = self._add_client("Bob")

        with patch.object(
            self.server.chatbot_manager,
            "chat",
            side_effect=ChatBotResponseError("Chatbot API returned invalid JSON."),
        ):
            with self.assertLogs("server.server", level="ERROR") as logs:
                self.server._handle_group_bot_mention("Alice", "@bot help")

        alice_message = self._read_message(alice_file)
        bob_message = self._read_message(bob_file)
        self.assertEqual(alice_message["content"], "Bot service returned an invalid response.")
        self.assertEqual(bob_message["content"], "Bot service returned an invalid response.")
        self.assertIn("Chatbot API returned invalid JSON.", "\n".join(logs.output))

    def test_chatbot_unexpected_failure_returns_generic_system_message(self) -> None:
        _alice_client, alice_file, _alice_server = self._add_client("Alice")
        _bob_client, bob_file, _bob_server = self._add_client("Bob")

        with patch.object(self.server.chatbot_manager, "chat", side_effect=RuntimeError("api down")):
            with self.assertLogs("server.server", level="ERROR") as logs:
                self.server._handle_group_bot_mention("Alice", "@bot help")

        alice_message = self._read_message(alice_file)
        bob_message = self._read_message(bob_file)
        self.assertEqual(alice_message["content"], "Bot failed unexpectedly. Check server logs.")
        self.assertEqual(bob_message["content"], "Bot failed unexpectedly. Check server logs.")
        self.assertIn("api down", "\n".join(logs.output))

    def test_server_logs_bot_startup_warning_when_ai_is_unconfigured(self) -> None:
        with self.assertLogs("server.server", level="WARNING") as logs:
            self.server._log_bot_startup_status()

        self.assertIn("Bot AI features are not configured", "\n".join(logs.output))

    def test_gui_error_mapping_is_friendly(self) -> None:
        self.assertEqual(
            GUIChatClient.friendly_server_error_message("Room abc not found."),
            "Game room not found.",
        )
        self.assertEqual(
            GUIChatClient.friendly_server_error_message("Game room not found."),
            "Game room not found.",
        )
        self.assertEqual(
            GUIChatClient.friendly_server_error_message("Invalid move. It is not your turn."),
            "Invalid move. It is not your turn.",
        )
        self.assertEqual(
            GUIChatClient.friendly_server_error_message("Invalid move (cell occupied or out of bounds)"),
            "Invalid move. Choose an empty cell.",
        )
        self.assertEqual(
            GUIChatClient.friendly_server_error_message("Bot is not configured on the server."),
            "Bot is not configured on the server.",
        )
        self.assertEqual(
            GUIChatClient.friendly_server_error_message("Bot service authentication failed."),
            "Bot service authentication failed.",
        )
        self.assertEqual(
            GUIChatClient.friendly_server_error_message("Bot service is unreachable right now."),
            "Bot service is unreachable right now.",
        )
        self.assertEqual(
            GUIChatClient.friendly_server_error_message("Bot service returned an invalid response."),
            "Bot service returned an invalid response.",
        )
        self.assertEqual(
            GUIChatClient.friendly_server_error_message("Bot failed unexpectedly. Check server logs."),
            "Bot failed unexpectedly. Check server logs.",
        )
        self.assertEqual(
            GUIChatClient.friendly_server_error_message("Bot is temporarily unavailable."),
            "Bot is temporarily unavailable.",
        )

    def test_emoji_shortcodes_expand_for_supported_tokens(self) -> None:
        self.assertEqual(
            GUIChatClient.expand_emoji_shortcodes("Nice work :thumbsup: :party:"),
            "Nice work 👍 🎉",
        )
        self.assertEqual(
            GUIChatClient.expand_emoji_shortcodes("@bot hello :think:"),
            "@bot hello 🤔",
        )

    def test_emoji_shortcodes_leave_unknown_text_unchanged(self) -> None:
        self.assertEqual(
            GUIChatClient.expand_emoji_shortcodes("plain text :unknown:"),
            "plain text :unknown:",
        )


if __name__ == "__main__":
    unittest.main()
