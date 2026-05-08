"""Local Tkinter game window for Tic-Tac-Toe."""

from __future__ import annotations

import json
import socket
import tkinter as tk
import threading

from game.tic_tac_toe import TicTacToe
from server.protocol import create_message, encode_message


class GameWindow:
    """Tkinter UI for a local two-player or multiplayer Tic-Tac-Toe game."""

    def __init__(
        self,
        socket_obj: socket.socket | None = None,
        room_id: str = "",
        player_symbol: str = "",
        username: str = "",
    ) -> None:
        self.root = tk.Tk()
        self.root.title("Tic-Tac-Toe")
        self.root.resizable(False, False)

        self.game = TicTacToe()
        self.status_var = tk.StringVar(value=self.game.get_status_text())
        self.result_var = tk.StringVar(value="")
        self.buttons: list[tk.Button] = []

        # Multiplayer support
        self.socket = socket_obj
        self.room_id = room_id
        self.player_symbol = player_symbol
        self.username = username or player_symbol
        self.is_local = socket_obj is None
        self.last_server_state: dict[str, object] | None = None
        self.last_game_over_text = ""

        self._build_ui()

        # Start listening for server messages if multiplayer
        if not self.is_local and self.socket:
            self._start_message_listener()

    def _build_ui(self) -> None:
        """Create the labels, board buttons, and restart control."""

        container = tk.Frame(self.root, padx=16, pady=16)
        container.pack()

        tk.Label(container, textvariable=self.status_var, font=("TkDefaultFont", 12, "bold")).pack(pady=(0, 6))
        tk.Label(container, textvariable=self.result_var, font=("TkDefaultFont", 11)).pack(pady=(0, 12))

        board_frame = tk.Frame(container)
        board_frame.pack()

        for row in range(3):
            for col in range(3):
                button = tk.Button(
                    board_frame,
                    text="",
                    width=8,
                    height=4,
                    font=("TkDefaultFont", 14, "bold"),
                    command=lambda r=row, c=col: self.on_cell_click(r, c),
                )
                button.grid(row=row, column=col, padx=3, pady=3)
                self.buttons.append(button)

        restart_button = tk.Button(container, text="Restart", command=self.reset_game)
        restart_button.pack(pady=(12, 0))

    def on_cell_click(self, row: int, col: int) -> None:
        """Handle a board click and update the UI."""

        if self.is_local:
            # Local game: make move directly
            if not self.game.make_move(row, col):
                return

            index = row * 3 + col
            self.buttons[index].config(text=self.game.board[index] or "", state="disabled")
            self._refresh_labels()
            if self.game.is_game_over():
                self._disable_board()
        else:
            # Multiplayer: send move to server
            self._send_game_move(row, col)

    def _send_game_move(self, row: int, col: int) -> None:
        """Send a game_move message to the server."""

        try:
            msg = create_message(
                "game_move",
                self.username,
                f"Move at ({row}, {col})",
                extra={"room_id": self.room_id, "row": row, "col": col},
            )
            self.socket.sendall(encode_message(msg))
        except Exception as e:
            self.result_var.set(f"Error sending move: {e}")

    def _start_message_listener(self) -> None:
        """Start a background thread to listen for server messages."""

        thread = threading.Thread(target=self._listen_for_messages, daemon=True)
        thread.start()

    def _listen_for_messages(self) -> None:
        """Listen for game_state and game_start messages from the server."""

        try:
            self.socket.settimeout(None)
            sock_file = self.socket.makefile("r", encoding="utf-8")

            for line in sock_file:
                try:
                    message = json.loads(line.strip())
                    msg_type = message.get("type")

                    if msg_type == "game_state":
                        self._handle_game_state(message)
                    elif msg_type == "game_start":
                        self._handle_game_start(message)
                    elif msg_type == "error":
                        self._handle_error(message)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"Message listener error: {e}")

    def _handle_game_start(self, message: dict) -> None:
        """Handle game_start message from server."""

        extra = message.get("extra", {})
        x_player = extra.get("x_player", "X")
        o_player = extra.get("o_player", "O")

        status = f"Game started: {x_player}(X) vs {o_player}(O)"
        self.root.after(0, lambda: self.status_var.set(status))

    def _handle_game_state(self, message: dict) -> None:
        """Handle game_state message from server and update the board."""

        extra = message.get("extra", {})
        board = extra.get("board")
        current_player = extra.get("current_player")
        winner = extra.get("winner")
        is_draw = extra.get("is_draw")
        is_game_over = extra.get("is_game_over")

        if board is None:
            return

        self.last_server_state = {
            "board": board,
            "current_player": current_player,
            "winner": winner,
            "is_draw": is_draw,
            "is_game_over": is_game_over,
        }

        if winner:
            self.last_game_over_text = f"Result: {winner} wins"
        elif is_draw:
            self.last_game_over_text = "Result: Draw"
        else:
            self.last_game_over_text = ""

        # Update the board in the UI
        self.root.after(0, lambda: self._update_board_from_state(board, current_player, winner, is_draw, is_game_over))

    def _handle_error(self, message: dict) -> None:
        """Handle error messages from the server."""

        content = message.get("content", "Unknown error")
        self.root.after(0, lambda: self.result_var.set(f"Error: {content}"))

    def _update_board_from_state(self, board: list, current_player: str, winner: str | None, is_draw: bool, is_game_over: bool) -> None:
        """Update the UI with the new board state from the server."""

        # Update board buttons
        for i, cell in enumerate(board):
            self.buttons[i].config(text=cell or "", state="disabled" if cell else "normal")

        # Update status
        if current_player:
            self.status_var.set(f"Current turn: {current_player}")

        # Update result if game is over
        if is_game_over:
            if winner:
                self.result_var.set(f"Result: {winner} wins")
            elif is_draw:
                self.result_var.set("Result: Draw")
            self._disable_board()

    def reset_game(self) -> None:
        """Restart the game and clear the board."""

        if self.is_local:
            self.game.reset_game()
            for button in self.buttons:
                button.config(text="", state="normal")
            self.result_var.set("")
            self._refresh_labels()
        else:
            self.result_var.set("Cannot reset multiplayer game")

    def _disable_board(self) -> None:
        """Disable every cell after the game ends."""

        for button in self.buttons:
            button.config(state="disabled")

        if self.is_local:
            if self.game.winner is not None:
                self.result_var.set(f"Result: {self.game.winner} wins")
            elif self.game.is_draw:
                self.result_var.set("Result: Draw")
            self.status_var.set(self.game.get_status_text())
            return

        if self.last_server_state is None:
            return

        current_player = self.last_server_state.get("current_player")
        if self.last_game_over_text:
            self.status_var.set(self.last_game_over_text)
            self.result_var.set(self.last_game_over_text)
        elif current_player:
            self.status_var.set(f"Current turn: {current_player}")

    def _refresh_labels(self) -> None:
        """Update the status label after each move."""

        if self.is_local:
            self.status_var.set(self.game.get_status_text())
        elif self.last_server_state is not None:
            current_player = self.last_server_state.get("current_player")
            if current_player:
                self.status_var.set(f"Current turn: {current_player}")

    def launch(self) -> None:
        """Start the Tkinter event loop."""

        self.root.mainloop()


def main() -> None:
    """Run the local game window."""

    GameWindow().launch()


if __name__ == "__main__":
    main()
