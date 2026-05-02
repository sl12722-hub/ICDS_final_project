"""Terminal chat client using the shared JSON protocol."""

from __future__ import annotations

import argparse
import socket
import threading

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

    if msg_type == "chat":
        return f"[{timestamp}] {sender}: {content}"

    return f"[{timestamp}] {msg_type.upper()} from {sender}: {content}"


def start_client(host: str, port: int, username: str) -> None:
    """Connect to the chat server and send user input as chat messages."""

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((host, port))

    receiver = threading.Thread(target=receive_messages, args=(client_socket,), daemon=True)
    receiver.start()

    print("Connected to server.")
    print("Type a chat message and press Enter. Type /quit to leave.")

    try:
        while True:
            user_input = input()
            if user_input.strip().lower() == "/quit":
                break

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
