"""Terminal chat client using the shared JSON protocol."""

from __future__ import annotations

import argparse
import socket
import threading

from bonus.sentiment import analyze_sentiment
from chatbot.chatbot_manager import ChatbotManager
from server.protocol import ProtocolError, create_message, decode_message, encode_message


def receive_messages(client_socket: socket.socket) -> None:
    """Read server messages forever and print them clearly."""

    client_file = client_socket.makefile("r", encoding="utf-8")

    try:
        for raw_line in client_file:
            try:
                message = decode_message(raw_line)
            except ProtocolError as error:
                print(f"[protocol error] {error}")
                continue

            print(format_message(message))
    except (ConnectionResetError, OSError):
        print("Connection to server was lost.")
    finally:
        try:
            client_file.close()
        except OSError:
            pass


def format_message(message: dict[str, str]) -> str:
    """Turn a message dictionary into readable terminal text."""

    msg_type = message["type"]
    sender = message["sender"]
    timestamp = message["timestamp"]
    content = message["content"]
    extra = message.get("extra", {})

    if msg_type == "chat":
        return f"[{timestamp}] {sender}: {content}"

    if msg_type == "sentiment_result":
        sentiment = ""
        if isinstance(extra, dict):
            sentiment = str(extra.get("sentiment", "")).strip()
        if not sentiment:
            sentiment = analyze_sentiment(content)
        return f"[{timestamp}] {sender}: {content} [{sentiment}]"

    if msg_type == "bot_response":
        return f"[{timestamp}] Bot: {content}"

    if msg_type in {"system", "error", "game_end", "summary_response", "keywords_response"}:
        return f"[{timestamp}] {content}"

    return f"[{timestamp}] {msg_type.upper()} from {sender}: {content}"


def start_client(host: str, port: int, username: str) -> None:
    """Connect to the chat server and send user input as chat messages."""

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((host, port))
    chatbot_manager = ChatbotManager()

    receiver = threading.Thread(target=receive_messages, args=(client_socket,), daemon=True)
    receiver.start()

    print("Connected to server.")
    print("Type a chat message and press Enter. Type /quit to leave.")

    try:
        while True:
            user_input = input()
            if user_input.strip().lower() == "/quit":
                break

            stripped_input = user_input.strip()
            if chatbot_manager.is_personality_command(stripped_input):
                personality_key = chatbot_manager.extract_personality_choice(stripped_input)
                if not personality_key:
                    print("Use /personality friendly, /personality funny, or /personality serious.")
                    continue
                message = create_message(
                    "bot_request",
                    username,
                    stripped_input,
                    extra={"action": "set_personality", "personality": personality_key},
                )
            elif chatbot_manager.is_bot_command(stripped_input):
                message = create_message("bot_request", username, stripped_input)
            else:
                message = create_message("chat", username, user_input)
            client_socket.sendall(encode_message(message))
    except KeyboardInterrupt:
        pass
    finally:
        try:
            client_socket.close()
        except OSError:
            pass


def parse_args() -> argparse.Namespace:
    """Read host, port, and username from the command line."""

    parser = argparse.ArgumentParser(description="Start a terminal chat client.")
    parser.add_argument("--host", default="127.0.0.1", help="Server IP address.")
    parser.add_argument("--port", type=int, default=12345, help="Server TCP port.")
    parser.add_argument("--username", required=True, help="Displayed chat username.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    start_client(args.host, args.port, args.username)
