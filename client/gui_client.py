"""Tkinter GUI chat client using the shared JSON protocol."""

from __future__ import annotations

import socket
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

from server.protocol import ProtocolError, create_message, decode_message, encode_message


class GUIChatClient:
    """Small GUI wrapper around the same chat socket protocol."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("ICDS Chat Client")
        self.root.geometry("700x500")

        self.client_socket: socket.socket | None = None
        self.receiver_thread: threading.Thread | None = None

        self.host_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.StringVar(value="12345")
        self.username_var = tk.StringVar()
        self.message_var = tk.StringVar()

        self.build_gui()
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)

    def build_gui(self) -> None:
        """Create the visible chat controls."""

        top_frame = tk.Frame(self.root, padx=10, pady=10)
        top_frame.pack(fill="x")

        tk.Label(top_frame, text="Host").grid(row=0, column=0, sticky="w")
        tk.Entry(top_frame, textvariable=self.host_var, width=15).grid(row=0, column=1, padx=5)

        tk.Label(top_frame, text="Port").grid(row=0, column=2, sticky="w")
        tk.Entry(top_frame, textvariable=self.port_var, width=8).grid(row=0, column=3, padx=5)

        tk.Label(top_frame, text="Username").grid(row=0, column=4, sticky="w")
        tk.Entry(top_frame, textvariable=self.username_var, width=15).grid(row=0, column=5, padx=5)

        self.connect_button = tk.Button(top_frame, text="Connect", command=self.connect_to_server)
        self.connect_button.grid(row=0, column=6, padx=5)

        self.chat_area = scrolledtext.ScrolledText(self.root, state="disabled", wrap="word")
        self.chat_area.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        bottom_frame = tk.Frame(self.root, padx=10, pady=10)
        bottom_frame.pack(fill="x")

        message_entry = tk.Entry(bottom_frame, textvariable=self.message_var)
        message_entry.pack(side="left", fill="x", expand=True)
        message_entry.bind("<Return>", lambda _event: self.send_message())

        self.send_button = tk.Button(bottom_frame, text="Send", command=self.send_message, state="disabled")
        self.send_button.pack(side="left", padx=(8, 0))

    def connect_to_server(self) -> None:
        """Open the socket connection and start receiving messages."""

        if self.client_socket is not None:
            return

        username = self.username_var.get().strip()
        if not username:
            messagebox.showerror("Missing username", "Please enter a username.")
            return

        try:
            host = self.host_var.get().strip()
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid port", "Port must be a whole number.")
            return

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
        except OSError as error:
            self.client_socket = None
            messagebox.showerror("Connection failed", str(error))
            return

        self.connect_button.config(state="disabled")
        self.send_button.config(state="normal")
        self.add_text("Connected to server.\n")

        self.receiver_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receiver_thread.start()

    def receive_messages(self) -> None:
        """Read messages in a background thread."""

        if self.client_socket is None:
            return

        client_file = self.client_socket.makefile("r", encoding="utf-8")

        try:
            for raw_line in client_file:
                try:
                    message = decode_message(raw_line)
                    display_text = self.format_message(message)
                except ProtocolError as error:
                    display_text = f"[protocol error] {error}\n"

                self.root.after(0, self.add_text, display_text)
        except (ConnectionResetError, OSError):
            self.root.after(0, self.add_text, "Connection to server was lost.\n")
        finally:
            try:
                client_file.close()
            except OSError:
                pass
            self.root.after(0, self.handle_disconnect)

    def send_message(self) -> None:
        """Send the current entry box text as a chat message."""

        if self.client_socket is None:
            return

        content = self.message_var.get().strip()
        if not content:
            return

        try:
            message = create_message("chat", self.username_var.get().strip(), content)
            self.client_socket.sendall(encode_message(message))
            self.message_var.set("")
        except OSError as error:
            messagebox.showerror("Send failed", str(error))
            self.handle_disconnect()

    def format_message(self, message: dict[str, str]) -> str:
        """Format protocol messages for the chat window."""

        if message["type"] == "chat":
            return f"[{message['timestamp']}] {message['sender']}: {message['content']}\n"

        return (
            f"[{message['timestamp']}] "
            f"{message['type'].upper()} from {message['sender']}: {message['content']}\n"
        )

    def add_text(self, text: str) -> None:
        """Append text to the chat area."""

        self.chat_area.config(state="normal")
        self.chat_area.insert("end", text)
        self.chat_area.see("end")
        self.chat_area.config(state="disabled")

    def handle_disconnect(self) -> None:
        """Reset the buttons after a disconnect."""

        if self.client_socket is not None:
            try:
                self.client_socket.close()
            except OSError:
                pass

        self.client_socket = None
        self.connect_button.config(state="normal")
        self.send_button.config(state="disabled")

    def close_window(self) -> None:
        """Close the socket first so the app exits cleanly."""

        self.handle_disconnect()
        self.root.destroy()

    def run(self) -> None:
        """Start the Tkinter event loop."""

        self.root.mainloop()


if __name__ == "__main__":
    GUIChatClient().run()
