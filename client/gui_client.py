"""Tkinter GUI chat client using the shared JSON protocol."""

from __future__ import annotations

import queue
import random
import socket
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

from chatbot.chatbot_manager import ChatbotManager
from server.protocol import ProtocolError, create_message, decode_message, encode_message


class GUIChatClient:
    """Small GUI wrapper around the same chat socket protocol."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("ICDS Chat Client")
        self.root.geometry("700x500")

        self.client_socket: socket.socket | None = None
        self.receiver_thread: threading.Thread | None = None
        self.bot_thread: threading.Thread | None = None
        self.window_closed = False
        self.ui_queue: queue.Queue[tuple[int, str, object | None]] = queue.Queue()
        self.queue_job_id: str | None = None
        self.connection_id = 0
        self.disconnect_requested = False
        self.chatbot_manager = ChatbotManager()

        self.host_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.StringVar(value="12345")
        self.username_var = tk.StringVar()
        self.message_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Status: Disconnected")

        self.build_gui()
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)
        self.queue_job_id = self.root.after(100, self.process_ui_queue)

    def build_gui(self) -> None:
        """Create the visible chat controls."""

        top_frame = tk.Frame(self.root, padx=10, pady=10)
        top_frame.pack(fill="x")

        tk.Label(top_frame, text="Host").grid(row=0, column=0, sticky="w")
        self.host_entry = tk.Entry(top_frame, textvariable=self.host_var, width=15)
        self.host_entry.grid(row=0, column=1, padx=5)

        tk.Label(top_frame, text="Port").grid(row=0, column=2, sticky="w")
        self.port_entry = tk.Entry(top_frame, textvariable=self.port_var, width=8)
        self.port_entry.grid(row=0, column=3, padx=5)

        tk.Label(top_frame, text="Username").grid(row=0, column=4, sticky="w")
        self.username_entry = tk.Entry(top_frame, textvariable=self.username_var, width=15)
        self.username_entry.grid(row=0, column=5, padx=5)

        self.connect_button = tk.Button(top_frame, text="Connect", command=self.connect_to_server)
        self.connect_button.grid(row=0, column=6, padx=5)

        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            padx=10,
            pady=4,
        )
        self.status_label.pack(fill="x")

        center_frame = tk.Frame(self.root, padx=10, pady=10)
        center_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.chat_area = scrolledtext.ScrolledText(center_frame, state="disabled", wrap="word")
        self.chat_area.pack(side="left", fill="both", expand=True)

        user_list_frame = tk.Frame(center_frame, padx=10)
        user_list_frame.pack(side="left", fill="y")
        tk.Label(user_list_frame, text="Online Users").pack(anchor="w")
        self.user_listbox = tk.Listbox(user_list_frame, width=18, height=18)
        self.user_listbox.pack(fill="y", expand=True)

        bottom_frame = tk.Frame(self.root, padx=10, pady=10)
        bottom_frame.pack(fill="x")

        self.message_entry = tk.Entry(bottom_frame, textvariable=self.message_var, state="disabled")
        self.message_entry.pack(side="left", fill="x", expand=True)
        self.message_entry.bind("<Return>", lambda _event: self.send_message())

        self.send_button = tk.Button(bottom_frame, text="Send", command=self.send_message, state="disabled")
        self.send_button.pack(side="left", padx=(8, 0))

    def connect_to_server(self) -> None:
        """Open the socket connection and start receiving messages."""

        if self.client_socket is not None:
            return

        username = self.resolve_username()

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
            self.status_var.set("Status: Connection failed")
            messagebox.showerror("Connection failed", str(error))
            return

        self.connection_id += 1
        self.disconnect_requested = False
        self.clear_ui_queue()
        self.connect_button.config(state="disabled")
        self.send_button.config(state="normal")
        self.host_entry.config(state="disabled")
        self.port_entry.config(state="disabled")
        self.username_entry.config(state="disabled")
        self.message_entry.config(state="normal")
        self.message_entry.focus_set()
        self.status_var.set(f"Status: Connected as {username}")
        self.add_text("Connected to server.\n")
        try:
            self.send_login_message(username)
        except OSError as error:
            self.status_var.set("Status: Disconnected")
            messagebox.showerror("Login failed", str(error))
            self.handle_disconnect()
            return

        self.receiver_thread = threading.Thread(
            target=self.receive_messages,
            args=(self.client_socket, self.connection_id),
            daemon=True,
        )
        self.receiver_thread.start()

    def receive_messages(self, client_socket: socket.socket, connection_id: int) -> None:
        """Read messages in a background thread."""

        client_file = client_socket.makefile("r", encoding="utf-8")

        try:
            for raw_line in client_file:
                try:
                    message = decode_message(raw_line)
                except ProtocolError as error:
                    self.ui_queue.put((connection_id, "text", f"[protocol error] {error}\n"))
                    continue

                # Each received message becomes one queue item and is discarded
                # after display, so old text is not re-inserted repeatedly.
                self.ui_queue.put((connection_id, "message", message))
        except (ConnectionResetError, OSError):
            if not self.disconnect_requested:
                self.ui_queue.put((connection_id, "text", "Connection to server was lost.\n"))
        finally:
            try:
                client_file.close()
            except OSError:
                pass
            self.ui_queue.put((connection_id, "disconnect", None))

    def send_message(self) -> None:
        """Send the current entry box text as a chat message."""

        content = self.message_var.get().strip()
        if not content:
            return

        if self.chatbot_manager.is_bot_command(content):
            self.message_var.set("")
            self.message_entry.focus_set()
            self.start_bot_request(content)
            return

        if self.client_socket is None:
            return

        try:
            message = create_message("chat", self.username_var.get().strip(), content)
            self.client_socket.sendall(encode_message(message))
            self.message_var.set("")
            self.message_entry.focus_set()
        except OSError as error:
            self.status_var.set("Status: Disconnected")
            messagebox.showerror("Send failed", str(error))
            self.handle_disconnect()

    def format_message(self, message: dict[str, object]) -> str:
        """Format protocol messages for the chat window."""

        if message["type"] == "chat":
            return f"{message['sender']}: {message['content']}\n"

        if message["type"] == "bot_response":
            return f"Bot: {message['content']}\n"

        if message["type"] == "system":
            return f"System: {message['content']}\n"

        if message["type"] == "error":
            return f"Error: {message['content']}\n"

        return f"{message['sender']}: {message['content']}\n"

    def add_text(self, text: str) -> None:
        """Append text to the chat area."""

        self.chat_area.config(state="normal")
        self.chat_area.insert("end", text)
        self.chat_area.see("end")
        self.chat_area.config(state="disabled")

    def handle_disconnect(self) -> None:
        """Reset the buttons after a disconnect."""

        self.disconnect_requested = True
        if self.client_socket is not None:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                self.client_socket.close()
            except OSError:
                pass

        self.client_socket = None
        self.connect_button.config(state="normal")
        self.send_button.config(state="disabled")
        self.host_entry.config(state="normal")
        self.port_entry.config(state="normal")
        self.username_entry.config(state="normal")
        self.message_entry.config(state="disabled")
        self.status_var.set("Status: Disconnected")
        self.update_user_list([])

    def process_ui_queue(self) -> None:
        """Apply background-thread updates from the main Tkinter thread."""

        if self.window_closed:
            return

        try:
            while True:
                connection_id, action, payload = self.ui_queue.get_nowait()
                if connection_id != self.connection_id:
                    continue
                if action == "text" and isinstance(payload, str):
                    self.add_text(payload)
                elif action == "message" and isinstance(payload, dict):
                    self.handle_server_message(payload)
                elif action == "bot_response" and isinstance(payload, str):
                    bot_message = create_message("bot_response", "Bot", payload)
                    self.add_text(self.format_message(bot_message))
                elif action == "disconnect":
                    self.handle_disconnect()
        except queue.Empty:
            pass

        try:
            self.queue_job_id = self.root.after(100, self.process_ui_queue)
        except (RuntimeError, tk.TclError):
            self.queue_job_id = None

    def clear_ui_queue(self) -> None:
        """Drop stale queued UI events before starting a new connection."""

        try:
            while True:
                self.ui_queue.get_nowait()
        except queue.Empty:
            pass

    def resolve_username(self) -> str:
        """Use a guest name when the user leaves the username field blank."""

        username = self.username_var.get().strip()
        if username:
            return username

        guest_name = f"Guest_{random.randint(1000, 9999)}"
        self.username_var.set(guest_name)
        return guest_name

    def send_login_message(self, username: str) -> None:
        """Tell the server which display name this client will use."""

        if self.client_socket is None:
            return

        login_message = create_message(
            "chat",
            username,
            "",
            extra={"event": "login"},
        )
        self.client_socket.sendall(encode_message(login_message))

    def handle_server_message(self, message: dict[str, object]) -> None:
        """Display one server message and refresh the optional user list."""

        extra = message.get("extra", {})
        if isinstance(extra, dict):
            user_list = extra.get("user_list")
            if isinstance(user_list, list):
                self.update_user_list(user_list)

        self.add_text(self.format_message(message))

    def update_user_list(self, user_list: list[str]) -> None:
        """Refresh the online user list panel."""

        self.user_listbox.delete(0, "end")
        for username in user_list:
            self.user_listbox.insert("end", username)

    def start_bot_request(self, command_text: str) -> None:
        """Launch chatbot work in a background thread so the GUI stays responsive."""

        self.add_text(f"{self.username_var.get().strip()}: {command_text}\n")
        self.bot_thread = threading.Thread(
            target=self.fetch_bot_response,
            args=(command_text,),
            daemon=True,
        )
        self.bot_thread.start()

    def fetch_bot_response(self, command_text: str) -> None:
        """Call the chatbot manager and queue the result for the GUI thread."""

        try:
            response_text = self.chatbot_manager.chat(command_text)
        except Exception as error:
            response_text = f"Sorry, the bot had a problem: {error}"

        self.ui_queue.put((self.connection_id, "bot_response", response_text))

    def close_window(self) -> None:
        """Close the socket first so the app exits cleanly."""

        self.window_closed = True
        if self.queue_job_id is not None:
            try:
                self.root.after_cancel(self.queue_job_id)
            except (RuntimeError, tk.TclError):
                pass
            self.queue_job_id = None
        self.handle_disconnect()
        self.root.destroy()

    def run(self) -> None:
        """Start the Tkinter event loop."""

        self.root.mainloop()


if __name__ == "__main__":
    GUIChatClient().run()
