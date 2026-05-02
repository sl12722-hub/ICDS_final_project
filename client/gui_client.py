"""Tkinter GUI chat client using the shared JSON protocol."""

from __future__ import annotations

import queue
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
        self.window_closed = False
        self.ui_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.queue_job_id: str | None = None

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

        self.chat_area = scrolledtext.ScrolledText(self.root, state="disabled", wrap="word")
        self.chat_area.pack(fill="both", expand=True, padx=10, pady=(0, 10))

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
            self.status_var.set("Status: Connection failed")
            messagebox.showerror("Connection failed", str(error))
            return

        self.connect_button.config(state="disabled")
        self.send_button.config(state="normal")
        self.host_entry.config(state="disabled")
        self.port_entry.config(state="disabled")
        self.username_entry.config(state="disabled")
        self.message_entry.config(state="normal")
        self.message_entry.focus_set()
        self.status_var.set(f"Status: Connected as {username}")
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

                self.ui_queue.put(("text", display_text))
        except (ConnectionResetError, OSError):
            self.ui_queue.put(("text", "Connection to server was lost.\n"))
        finally:
            try:
                client_file.close()
            except OSError:
                pass
            self.ui_queue.put(("disconnect", None))

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
            self.message_entry.focus_set()
        except OSError as error:
            self.status_var.set("Status: Disconnected")
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

    def process_ui_queue(self) -> None:
        """Apply background-thread updates from the main Tkinter thread."""

        if self.window_closed:
            return

        try:
            while True:
                action, payload = self.ui_queue.get_nowait()
                if action == "text" and payload is not None:
                    self.add_text(payload)
                elif action == "disconnect":
                    self.handle_disconnect()
        except queue.Empty:
            pass

        try:
            self.queue_job_id = self.root.after(100, self.process_ui_queue)
        except (RuntimeError, tk.TclError):
            self.queue_job_id = None

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
