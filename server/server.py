"""Threaded socket chat server using the shared JSON protocol."""

from __future__ import annotations

import argparse
import socket
import threading
from dataclasses import dataclass

from server.protocol import MESSAGE_TYPES, ProtocolError, create_message, decode_message, encode_message


@dataclass
class ClientConnection:
    """Store the socket and current username for one connected client."""

    socket: socket.socket
    file_obj: socket.SocketIO
    address: tuple[str, int]
    name: str


class ChatServer:
    """Simple multi-client chat server with one shared message format."""

    def __init__(self, host: str = "0.0.0.0", port: int = 12345) -> None:
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients: dict[socket.socket, ClientConnection] = {}
        self.name_to_socket: dict[str, socket.socket] = {}
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
        client = ClientConnection(client_socket, client_file, address, default_name)

        with self.lock:
            self.clients[client_socket] = client

        self.send_system_message(
            f"{default_name} connected.",
            target_socket=client_socket,
            target_name=default_name,
        )

        try:
            for raw_line in client_file:
                try:
                    message = decode_message(raw_line)
                except ProtocolError as error:
                    self.send_error(str(error), client_socket)
                    continue

                self._update_client_name(client_socket, message["sender"])
                self.route_message(client_socket, message)
        except (ConnectionResetError, OSError):
            pass
        finally:
            self.remove_client(client_socket)

    def route_message(self, source_socket: socket.socket, message: dict[str, str]) -> None:
        """Handle known message types and safely reject unknown ones."""

        msg_type = message["type"]

        if msg_type not in MESSAGE_TYPES:
            self.send_error(f"Unknown message type: {msg_type}", source_socket)
            return

        if msg_type == "system":
            self.send_error("Clients cannot send system messages.", source_socket)
            return

        if msg_type == "error":
            return

        target = message["target"]
        if target == "all":
            self.broadcast(message)
            return

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
    ) -> None:
        """Create and send a system message using the shared protocol."""

        message = create_message("system", "Server", content, target=target_name)
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

        self.send_system_message(f"{client.name} disconnected.")

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
