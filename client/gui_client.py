"""Tkinter GUI chat client using the shared JSON protocol."""

from __future__ import annotations

import queue
import random
import socket
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext

from bonus.ai_picture import show_image_preview, try_aipic_reply
from chatbot.chatbot_manager import ChatbotManager
from game.game_window import GameWindow
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
        self.project_root = Path(__file__).resolve().parents[1]

        self.host_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.StringVar(value="12345")
        self.username_var = tk.StringVar()
        self.personality_var = tk.StringVar(value=self.chatbot_manager.get_personality_label(None))
        self.message_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Status: Disconnected")
        self.game_room_var = tk.StringVar()
        self.game_status_var = tk.StringVar(value="Game: Not in room")
        self.current_room_id = ""
        self.active_game_window: GameWindow | None = None
        self.active_game_symbol = ""

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

        tk.Label(top_frame, text="Bot Personality").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.personality_menu = tk.OptionMenu(
            top_frame,
            self.personality_var,
            self.personality_var.get(),
            *self.chatbot_manager.get_personality_labels(),
            command=self.on_personality_selected,
        )
        self.personality_menu.config(width=18)
        self.personality_menu.grid(row=1, column=1, columnspan=3, sticky="w", pady=(8, 0))

        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            padx=10,
            pady=4,
        )
        self.status_label.pack(fill="x")

        game_frame = tk.LabelFrame(self.root, text="Game", padx=10, pady=8)
        game_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.create_game_button = tk.Button(game_frame, text="Create Game", command=self.create_game_room, state="disabled")
        self.create_game_button.grid(row=0, column=0, padx=(0, 8), pady=2)

        tk.Label(game_frame, text="Room ID").grid(row=0, column=1, sticky="w")
        self.room_id_entry = tk.Entry(game_frame, textvariable=self.game_room_var, width=16, state="disabled")
        self.room_id_entry.grid(row=0, column=2, padx=6, pady=2)

        self.join_game_button = tk.Button(game_frame, text="Join Game", command=self.join_game_room, state="disabled")
        self.join_game_button.grid(row=0, column=3, padx=(2, 0), pady=2)

        tk.Label(game_frame, textvariable=self.game_status_var, anchor="w").grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(6, 0),
        )

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
        self.create_game_button.config(state="normal")
        self.join_game_button.config(state="normal")
        self.host_entry.config(state="disabled")
        self.port_entry.config(state="disabled")
        self.username_entry.config(state="disabled")
        self.room_id_entry.config(state="normal")
        self.message_entry.config(state="normal")
        self.message_entry.focus_set()
        self.status_var.set(f"Status: Connected as {username}")
        self.add_text("Connected to server.\n")
        self.sync_personality_selection(username)
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

        if self.chatbot_manager.is_personality_command(content):
            self.message_var.set("")
            self.message_entry.focus_set()
            self.handle_personality_command(content)
            return

        aipic_reply = try_aipic_reply(content, output_root=self.project_root)
        if aipic_reply is not None:
            self.message_var.set("")
            self.message_entry.focus_set()
            self.show_local_system_message(aipic_reply)
            if aipic_reply.startswith("Generated image saved: "):
                relative_path = aipic_reply.split(": ", 1)[1].strip()
                show_image_preview(str(self.project_root / relative_path), master=self.root)
            return

        # NOTE: Do not handle @bot locally. Send mentions to the server so
        # the server can coordinate a single group reply and broadcast it.

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
            content = str(message.get("content", ""))
            if not content.strip():
                return f"{message['sender']}: {content}\n"
            sentiment_label = analyze_sentiment(content)
            return f"{message['sender']}: {content} [{sentiment_label}]\n"

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
        self.create_game_button.config(state="disabled")
        self.join_game_button.config(state="disabled")
        self.host_entry.config(state="normal")
        self.port_entry.config(state="normal")
        self.username_entry.config(state="normal")
        self.room_id_entry.config(state="disabled")
        self.message_entry.config(state="disabled")
        self.status_var.set("Status: Disconnected")
        self.game_status_var.set("Game: Not in room")
        self.current_room_id = ""
        self.active_game_symbol = ""
        self.update_user_list([])

    def create_game_room(self) -> None:
        """Send a game_create request using the current socket."""

        if self.client_socket is None:
            return

        username = self.username_var.get().strip()
        if not username:
            return

        try:
            message = create_message("game_create", username, "create room")
            self.client_socket.sendall(encode_message(message))
            self.game_status_var.set("Game: Creating room...")
        except OSError as error:
            self.status_var.set("Status: Disconnected")
            messagebox.showerror("Create game failed", str(error))
            self.handle_disconnect()

    def join_game_room(self) -> None:
        """Send a game_join request with the room ID from input."""

        if self.client_socket is None:
            return

        username = self.username_var.get().strip()
        room_id = self.game_room_var.get().strip()
        if not username or not room_id:
            return

        try:
            message = create_message(
                "game_join",
                username,
                f"join {room_id}",
                extra={"room_id": room_id},
            )
            self.client_socket.sendall(encode_message(message))
            self.game_status_var.set(f"Game: Joining room {room_id}...")
        except OSError as error:
            self.status_var.set("Status: Disconnected")
            messagebox.showerror("Join game failed", str(error))
            self.handle_disconnect()

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

    def get_chatbot_user_key(self) -> str:
        """Return the current chatbot user key without forcing a guest name."""

        return self.username_var.get().strip() or "local_user"

    def sync_personality_selection(self, user_key: str | None = None) -> None:
        """Copy the GUI dropdown value into the chatbot manager."""

        personality_key = self.chatbot_manager.personality_key_from_label(self.personality_var.get())
        self.chatbot_manager.set_personality(user_key or self.get_chatbot_user_key(), personality_key)

    def show_local_system_message(self, text: str) -> None:
        """Display a system message that only belongs in this GUI."""

        system_message = create_message("system", "System", text)
        self.add_text(self.format_message(system_message))

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

        self.handle_game_message(message)

        self.add_text(self.format_message(message))

    def handle_game_message(self, message: dict[str, object]) -> None:
        """Handle game protocol messages and drive game UI state."""

        msg_type = str(message.get("type", ""))
        extra = message.get("extra", {})
        if not isinstance(extra, dict):
            return

        if msg_type == "game_create":
            room_id = str(extra.get("room_id", "")).strip()
            if room_id:
                self.current_room_id = room_id
                self.game_room_var.set(room_id)
                self.game_status_var.set(f"Game: Room {room_id} created")

        elif msg_type == "game_start":
            room_id = str(extra.get("room_id", "")).strip()
            x_player = str(extra.get("x_player", "")).strip()
            o_player = str(extra.get("o_player", "")).strip()
            username = self.username_var.get().strip()

            symbol = ""
            if username and username == x_player:
                symbol = "X"
            elif username and username == o_player:
                symbol = "O"

            self.current_room_id = room_id
            self.active_game_symbol = symbol
            self.game_room_var.set(room_id)
            self.game_status_var.set(f"Game: Started in room {room_id} as {symbol or '?'}")
            self.open_game_window(room_id, symbol)
            if self.active_game_window is not None:
                self.active_game_window.handle_server_message(message)

        elif msg_type == "game_state":
            if self.active_game_window is not None:
                self.active_game_window.handle_server_message(message)

            winner = extra.get("winner")
            is_draw = bool(extra.get("is_draw", False))
            is_game_over = bool(extra.get("is_game_over", False))
            if is_game_over:
                if winner:
                    self.game_status_var.set(f"Game: Winner {winner}")
                    self.add_text(f"System: Game result - {winner} wins\n")
                elif is_draw:
                    self.game_status_var.set("Game: Draw")
                    self.add_text("System: Game result - Draw\n")

        elif msg_type == "error":
            text = str(message.get("content", ""))
            if "game" in text.lower() or "room" in text.lower() or "turn" in text.lower() or "move" in text.lower():
                self.game_status_var.set(f"Game: {text}")

    def open_game_window(self, room_id: str, symbol: str) -> None:
        """Open (or focus) the game window without blocking the chat GUI."""

        if self.client_socket is None:
            return

        if self.active_game_window is not None:
            try:
                self.active_game_window.root.lift()
                self.active_game_window.root.focus_force()
                return
            except tk.TclError:
                self.active_game_window = None

        self.active_game_window = GameWindow(
            socket_obj=self.client_socket,
            room_id=room_id,
            player_symbol=symbol,
            username=self.username_var.get().strip(),
            parent=self.root,
            auto_listen=False,
        )
        self.active_game_window.root.bind("<Destroy>", self._on_game_window_destroy, add="+")

    def _on_game_window_destroy(self, _event: tk.Event) -> None:
        """Forget closed game window instances."""

        if self.active_game_window is None:
            return
        try:
            if not self.active_game_window.root.winfo_exists():
                self.active_game_window = None
        except tk.TclError:
            self.active_game_window = None

    def update_user_list(self, user_list: list[str]) -> None:
        """Refresh the online user list panel."""

        self.user_listbox.delete(0, "end")
        for username in user_list:
            self.user_listbox.insert("end", username)

    def start_bot_request(self, command_text: str) -> None:
        """Launch chatbot work in a background thread so the GUI stays responsive."""

        user_key = self.get_chatbot_user_key()
        self.sync_personality_selection(user_key)
        self.add_text(f"{self.username_var.get().strip()}: {command_text}\n")
        self.bot_thread = threading.Thread(
            target=self.fetch_bot_response,
            args=(user_key, command_text),
            daemon=True,
        )
        self.bot_thread.start()

    def fetch_bot_response(self, user_key: str, command_text: str) -> None:
        """Call the chatbot manager and queue the result for the GUI thread."""

        try:
            response_text = self.chatbot_manager.chat(user_key, command_text)
        except Exception as error:
            response_text = f"Sorry, the bot had a problem: {error}"

        self.ui_queue.put((self.connection_id, "bot_response", response_text))

    def handle_personality_command(self, command_text: str) -> None:
        """Apply a personality command and show the result locally."""

        user_key = self.get_chatbot_user_key()
        result_text = self.chatbot_manager.handle_personality_command(user_key, command_text)
        self.personality_var.set(self.chatbot_manager.get_personality_label(user_key))
        self.show_local_system_message(result_text)

    def on_personality_selected(self, selected_label: str) -> None:
        """Update the chatbot manager when the dropdown changes."""

        self.personality_var.set(selected_label)
        self.sync_personality_selection()
        self.show_local_system_message(f"Bot personality set to {selected_label}.")

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
