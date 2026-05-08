"""Threaded socket chat server using the shared JSON protocol."""

from __future__ import annotations

import argparse
import re
import socket
import threading
from dataclasses import dataclass

from chatbot.chatbot_manager import ChatbotManager
from bonus.summary_keywords import extract_keywords, summarize_chat
from server.chat_history import ChatHistory
from server.game_manager import GameManager
from server.protocol import MESSAGE_TYPES, ProtocolError, create_message, decode_message, encode_message


@dataclass
class ClientConnection:
    """Store the socket and current username for one connected client."""

    socket: socket.socket
    file_obj: socket.SocketIO
    address: tuple[str, int]
    name: str
    has_announced_join: bool


class ChatServer:
    """Simple multi-client chat server with one shared message format."""

    def __init__(self, host: str = "0.0.0.0", port: int = 12345) -> None:
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients: dict[socket.socket, ClientConnection] = {}
        self.name_to_socket: dict[str, socket.socket] = {}
        self.chatbot_manager = ChatbotManager()
        self.chat_history = ChatHistory()
        self.game_manager = GameManager()
        self.history_limit = 12
        self.bot_mention_pattern = re.compile(r"(?i)(?<!\w)@bot\b")
        self.lock = threading.Lock()

    def start(self) -> None:
        """Bind the server socket and accept clients forever."""

        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Server listening on {self.host}:{self.port}")

        try:
            while True:
                client_socket, address = self.server_socket.accept()
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address),
                    daemon=True,
                )
                thread.start()
        except KeyboardInterrupt:
            print("\nServer shutting down.")
        finally:
            self.shutdown()

    def handle_client(self, client_socket: socket.socket, address: tuple[str, int]) -> None:
        """Receive, decode, and route messages from one client."""

        client_file = client_socket.makefile("r", encoding="utf-8")
        default_name = f"{address[0]}:{address[1]}"
        client = ClientConnection(client_socket, client_file, address, default_name, False)

        with self.lock:
            self.clients[client_socket] = client

        try:
            for raw_line in client_file:
                try:
                    message = decode_message(raw_line)
                except ProtocolError as error:
                    self.send_error(str(error), client_socket)
                    continue

                self.route_message(client_socket, message)
        except (ConnectionResetError, OSError):
            pass
        finally:
            self.remove_client(client_socket)

    def route_message(self, source_socket: socket.socket, message: dict[str, str]) -> None:
        """Handle known message types and safely reject unknown ones."""

        msg_type = message["type"]
        extra = message["extra"]
        content = str(message.get("content", ""))
        normalized_content = content.strip().lower()

        if msg_type not in MESSAGE_TYPES:
            self.send_error(f"Unknown message type: {msg_type}", source_socket)
            return

        if msg_type == "system":
            self.send_error("Clients cannot send system messages.", source_socket)
            return

        if msg_type == "error":
            return

        if msg_type in {"game_state", "game_end"}:
            return

        if self._is_summary_request(msg_type, normalized_content):
            sender_name = self._normalize_name(message["sender"], source_socket)
            self._update_client_name(source_socket, sender_name)
            self._announce_join_if_needed(source_socket)
            self._handle_summary_request()
            return

        if self._is_keywords_request(msg_type, normalized_content):
            sender_name = self._normalize_name(message["sender"], source_socket)
            self._update_client_name(source_socket, sender_name)
            self._announce_join_if_needed(source_socket)
            self._handle_keywords_request()
            return

        sender_name = self._normalize_name(message["sender"], source_socket)
        self._update_client_name(source_socket, sender_name)
        if extra.get("event") == "login":
            self._announce_join_if_needed(source_socket)
            return

        if msg_type == "game_create":
            self._handle_game_create(source_socket, sender_name)
            return

        if msg_type == "game_join":
            room_id = str(extra.get("room_id", "")).strip()
            self._handle_game_join(source_socket, sender_name, room_id)
            return

        if msg_type == "game_move":
            room_id = str(extra.get("room_id", "")).strip()
            row = int(extra.get("row", -1))
            col = int(extra.get("col", -1))
            self._handle_game_move(source_socket, sender_name, room_id, row, col)
            return

        self._announce_join_if_needed(source_socket)
        target = message["target"]
        if target == "all":
            message["sender"] = sender_name
            self.broadcast(message)
            self._record_group_message(message)

            if self._should_trigger_group_bot(message):
                thread = threading.Thread(
                    target=self._handle_group_bot_mention,
                    args=(sender_name, message["content"]),
                    daemon=True,
                )
                thread.start()
            return

        message["sender"] = sender_name
        delivered = self.send_to_target(target, message)
        if not delivered:
            self.send_error(f"Target user '{target}' is not connected.", source_socket)

    def broadcast(self, message: dict[str, str], exclude_socket: socket.socket | None = None) -> None:
        """Send one protocol message to all connected clients."""

        encoded = encode_message(message)
        with self.lock:
            recipients = list(self.clients.values())

        for client in recipients:
            if exclude_socket is not None and client.socket == exclude_socket:
                continue
            self._safe_send_bytes(client.socket, encoded)

    def send_to_target(self, target_name: str, message: dict[str, str]) -> bool:
        """Send one protocol message to one specific connected client."""

        with self.lock:
            target_socket = self.name_to_socket.get(target_name)

        if target_socket is None:
            return False

        self._safe_send_bytes(target_socket, encode_message(message))
        return True

    def send_system_message(
        self,
        content: str,
        target_socket: socket.socket | None = None,
        target_name: str = "all",
        extra: dict[str, object] | None = None,
    ) -> None:
        """Create and send a system message using the shared protocol."""

        message = create_message("system", "System", content, target=target_name, extra=extra)
        if target_socket is not None:
            self._safe_send_bytes(target_socket, encode_message(message))
            return
        self.broadcast(message)

    def send_error(self, content: str, target_socket: socket.socket) -> None:
        """Send a protocol error message back to one client."""

        target_name = self._socket_name(target_socket)
        message = create_message(
            "error",
            "Server",
            content,
            target=target_name,
            extra={"reason": content},
        )
        self._safe_send_bytes(target_socket, encode_message(message))

    def remove_client(self, client_socket: socket.socket) -> None:
        """Clean up one disconnected client and notify the remaining users."""

        with self.lock:
            client = self.clients.pop(client_socket, None)
            if client is not None:
                self.name_to_socket.pop(client.name, None)
                self.game_manager.remove_player(client.name)

        if client is None:
            return

        try:
            client.file_obj.close()
        except OSError:
            pass

        try:
            client_socket.close()
        except OSError:
            pass

        if client.has_announced_join:
            self.send_system_message(
                f"{client.name} left the chat",
                extra={"user_list": self.get_online_users()},
            )

    def shutdown(self) -> None:
        """Close all sockets when the server stops."""

        with self.lock:
            client_sockets = list(self.clients.keys())

        for client_socket in client_sockets:
            self.remove_client(client_socket)

        try:
            self.server_socket.close()
        except OSError:
            pass

    def _update_client_name(self, client_socket: socket.socket, new_name: str) -> None:
        """Track the latest username so direct messages can work later."""

        if not new_name:
            return

        with self.lock:
            client = self.clients.get(client_socket)
            if client is None:
                return

            old_name = client.name
            if old_name != new_name:
                self.name_to_socket.pop(old_name, None)
                client.name = new_name
                self.name_to_socket[new_name] = client_socket
            elif new_name not in self.name_to_socket:
                self.name_to_socket[new_name] = client_socket

    def _announce_join_if_needed(self, client_socket: socket.socket) -> None:
        """Broadcast a join message only once for each connected client."""

        with self.lock:
            client = self.clients.get(client_socket)
            if client is None or client.has_announced_join:
                return
            client.has_announced_join = True
            client_name = client.name

        self.send_system_message(
            f"{client_name} joined the chat",
            extra={"user_list": self.get_online_users()},
        )

    def _should_trigger_group_bot(self, message: dict[str, str]) -> bool:
        """Return True when a public chat message mentions the bot."""

        if message.get("type") != "chat":
            return False

        sender = str(message.get("sender", "")).strip().lower()
        if not sender or sender == "bot":
            return False

        content = str(message.get("content", ""))
        return bool(content.strip() and self.bot_mention_pattern.search(content))

    def _record_group_message(self, message: dict[str, str]) -> None:
        """Store a public message so bot prompts can use recent context.
        
        Only saves "chat" and "bot_response" messages. Game-related messages
        (game_move, game_state, etc.) are not saved to avoid cluttering history.
        """

        msg_type = str(message.get("type", "")).strip()
        
        # Only save chat and bot response messages to history
        if msg_type not in ("chat", "bot_response"):
            return
        
        # Extract key fields and add to history with timestamp
        sender = str(message.get("sender", "")).strip()
        content = str(message.get("content", "")).strip()
        timestamp = str(message.get("timestamp", "")).strip()
        
        with self.lock:
            self.chat_history.add_message(
                sender=sender,
                content=content,
                msg_type=msg_type,
                timestamp=timestamp,
            )

    def _is_summary_request(self, msg_type: str, normalized_content: str) -> bool:
        """Return True when an incoming message asks for a chat summary."""

        return msg_type == "summary_request" or (msg_type == "chat" and normalized_content == "/summary")

    def _is_keywords_request(self, msg_type: str, normalized_content: str) -> bool:
        """Return True when an incoming message asks for keywords."""

        return msg_type == "keywords_request" or (msg_type == "chat" and normalized_content == "/keywords")

    def _handle_summary_request(self) -> None:
        """Analyze recent chat and broadcast a short system summary."""

        with self.lock:
            history_text = self.chat_history.get_recent_text(self.history_limit)

        summary_text = summarize_chat(history_text)
        self.send_system_message(f"Summary: {summary_text}")

    def _handle_keywords_request(self) -> None:
        """Analyze recent chat and broadcast a keyword list."""

        with self.lock:
            history_text = self.chat_history.get_recent_text(self.history_limit)

        keywords = extract_keywords(history_text)
        if keywords:
            content = f"Keywords: {', '.join(keywords)}"
        else:
            content = "Keywords: No recent chat history to analyze."

        self.send_system_message(content)

    def _get_recent_group_messages(self) -> list[dict[str, object]]:
        """Return a small snapshot of recent group messages."""

        with self.lock:
            messages = self.chat_history.get_messages()

        if len(messages) <= self.history_limit:
            return messages

        return messages[-self.history_limit :]

    def _format_group_history(self, messages: list[dict[str, object]]) -> str:
        """Turn recent messages into readable prompt context."""

        lines: list[str] = []
        for item in messages:
            msg_type = str(item.get("type", ""))
            content = str(item.get("content", "")).strip()
            if not content:
                continue

            sender = str(item.get("sender", "")).strip() or "Unknown"
            if msg_type == "chat":
                lines.append(f"{sender}: {content}")
            elif msg_type == "bot_response":
                lines.append(f"Bot: {content}")

        return "\n".join(lines)

    def _build_group_bot_prompt(self, sender_name: str, current_message: str) -> str:
        """Combine the current mention with recent group history."""

        cleaned_message = self.bot_mention_pattern.sub("", current_message or "", count=1).strip()
        recent_history = self._format_group_history(self._get_recent_group_messages())

        prompt_lines = [f"@bot {cleaned_message or 'Please respond to the group.'}"]
        if recent_history:
            prompt_lines.append("")
            prompt_lines.append("Recent group chat history:")
            prompt_lines.append(recent_history)

        return "\n".join(prompt_lines)

    def _handle_group_bot_mention(self, sender_name: str, current_message: str) -> None:
        """Generate and broadcast one bot response for a group mention."""

        prompt_text = self._build_group_bot_prompt(sender_name, current_message)
        try:
            response_text = self.chatbot_manager.chat(sender_name, prompt_text)
        except Exception as error:
            response_text = f"Sorry, the bot had a problem: {error}"

        bot_message = create_message("bot_response", "Bot", response_text)
        self.broadcast(bot_message)
        self._record_group_message(bot_message)

    def _handle_game_create(self, creator_socket: socket.socket, creator_name: str) -> None:
        """Create a new game room and send the room ID to the creator."""

        room_id = self.game_manager.create_room(creator_name, creator_socket)
        if not room_id:
            error_message = create_message(
                "error",
                "Server",
                "You are already in a game.",
                target=creator_name,
            )
            self._safe_send_bytes(creator_socket, encode_message(error_message))
            return

        create_message_obj = create_message(
            "game_create",
            "Server",
            f"Room created: {room_id}",
            target=creator_name,
            extra={"room_id": room_id},
        )
        self._safe_send_bytes(creator_socket, encode_message(create_message_obj))

    def _handle_game_join(self, joiner_socket: socket.socket, joiner_name: str, room_id: str) -> None:
        """Join an existing game room and send game_start to both players if room is now full."""

        success, result = self.game_manager.join_room(room_id, joiner_name, joiner_socket)
        if not success:
            error_message = create_message(
                "error",
                "Server",
                result,
                target=joiner_name,
            )
            self._safe_send_bytes(joiner_socket, encode_message(error_message))
            return

        room = self.game_manager.get_room(room_id)
        if room is None:
            return

        game_start_message = create_message(
            "game_start",
            "Server",
            f"Game started: {room.x_player_name}(X) vs {room.o_player_name}(O)",
            extra={
                "room_id": room_id,
                "x_player": room.x_player_name,
                "o_player": room.o_player_name,
            },
        )

        self._safe_send_bytes(room.x_socket, encode_message(game_start_message))
        self._safe_send_bytes(room.o_socket, encode_message(game_start_message))

    def _handle_game_move(
        self, player_socket: socket.socket, player_name: str, room_id: str, row: int, col: int
    ) -> None:
        """Handle a player's move and broadcast the updated game state to both players."""

        success, result = self.game_manager.handle_move(room_id, player_name, row, col)
        if not success:
            error_message = create_message("error", "Server", result.get("error", "Move failed"), target=player_name)
            self._safe_send_bytes(player_socket, encode_message(error_message))
            return

        # Get the room to send state to both players
        room = self.game_manager.get_room(room_id)
        if not room or not room.game:
            return

        # Build game_state message with full board information
        game_state_message = create_message(
            "game_state",
            "Server",
            f"Game state updated",
            extra={
                "room_id": room_id,
                "board": result["board"],
                "current_player": result["current_player"],
                "winner": result["winner"],
                "is_draw": result["is_draw"],
                "is_game_over": result["is_game_over"],
                "x_player": room.x_player_name,
                "o_player": room.o_player_name,
            },
        )

        # Broadcast to both players
        self._safe_send_bytes(room.x_socket, encode_message(game_state_message))
        self._safe_send_bytes(room.o_socket, encode_message(game_state_message))

    def _normalize_name(self, requested_name: str, client_socket: socket.socket) -> str:
        """Use a readable guest name when the sender field is empty."""

        cleaned_name = requested_name.strip()
        if cleaned_name:
            return cleaned_name

        return f"Guest_{id(client_socket) % 10000:04d}"

    def get_online_users(self) -> list[str]:
        """Return the current connected usernames for the GUI user list."""

        with self.lock:
            return sorted(client.name for client in self.clients.values() if client.has_announced_join)

    def _safe_send_bytes(self, target_socket: socket.socket, payload: bytes) -> None:
        """Send bytes without letting send failures crash the server."""

        try:
            target_socket.sendall(payload)
        except OSError:
            self.remove_client(target_socket)

    def _socket_name(self, client_socket: socket.socket) -> str:
        """Return the current username for one socket."""

        with self.lock:
            client = self.clients.get(client_socket)

        if client is None:
            return "unknown"

        return client.name


def parse_args() -> argparse.Namespace:
    """Read optional host and port values from the command line."""

    parser = argparse.ArgumentParser(description="Start the ICDS chat server.")
    parser.add_argument("--host", default="0.0.0.0", help="IP address to bind.")
    parser.add_argument("--port", type=int, default=12345, help="TCP port to listen on.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ChatServer(args.host, args.port).start()
