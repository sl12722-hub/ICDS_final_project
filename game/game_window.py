"""Local Tkinter game window for Tic-Tac-Toe."""

from __future__ import annotations

import tkinter as tk

from game.tic_tac_toe import TicTacToe


class GameWindow:
    """Tkinter UI for a local two-player Tic-Tac-Toe game."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Tic-Tac-Toe")
        self.root.resizable(False, False)

        self.game = TicTacToe()
        self.status_var = tk.StringVar(value=self.game.get_status_text())
        self.result_var = tk.StringVar(value="")
        self.buttons: list[tk.Button] = []

        self._build_ui()

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

        if not self.game.make_move(row, col):
            return

        index = row * 3 + col
        self.buttons[index].config(text=self.game.board[index] or "", state="disabled")
        self._refresh_labels()
        if self.game.is_game_over():
            self._disable_board()

    def reset_game(self) -> None:
        """Restart the game and clear the board."""

        self.game.reset_game()
        for button in self.buttons:
            button.config(text="", state="normal")
        self.result_var.set("")
        self._refresh_labels()

    def _disable_board(self) -> None:
        """Disable every cell after the game ends."""

        for button in self.buttons:
            button.config(state="disabled")

        if self.game.winner is not None:
            self.result_var.set(f"Result: {self.game.winner} wins")
        elif self.game.is_draw:
            self.result_var.set("Result: Draw")

        self.status_var.set(self.game.get_status_text())

    def _refresh_labels(self) -> None:
        """Update the status label after each move."""

        self.status_var.set(self.game.get_status_text())

    def launch(self) -> None:
        """Start the Tkinter event loop."""

        self.root.mainloop()


def main() -> None:
    """Run the local game window."""

    GameWindow().launch()


if __name__ == "__main__":
    main()
