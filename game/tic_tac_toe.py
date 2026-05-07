"""Local Tic-Tac-Toe game logic."""

from __future__ import annotations


class TicTacToe:
    """Maintain Tic-Tac-Toe state and apply game rules."""

    WINNING_LINES = (
        (0, 1, 2),
        (3, 4, 5),
        (6, 7, 8),
        (0, 3, 6),
        (1, 4, 7),
        (2, 5, 8),
        (0, 4, 8),
        (2, 4, 6),
    )

    def __init__(self) -> None:
        self.reset_game()

    def reset_game(self) -> None:
        """Reset board state and the current player."""

        self.board: list[str | None] = [None] * 9
        self.current_player = "X"
        self.winner: str | None = None
        self.is_draw = False

    def make_move(self, row: int, col: int) -> bool:
        """Place the current player's mark if the move is valid."""

        index = row * 3 + col
        if not self._is_valid_index(index):
            return False
        if self.board[index] is not None or self.winner is not None or self.is_draw:
            return False

        self.board[index] = self.current_player
        self.winner = self.check_winner()
        if self.winner is None and all(cell is not None for cell in self.board):
            self.is_draw = True
        elif self.winner is None:
            self.current_player = "O" if self.current_player == "X" else "X"

        return True

    def check_winner(self) -> str | None:
        """Return the winning player symbol, or None if there is no winner."""

        for line in self.WINNING_LINES:
            first, second, third = line
            value = self.board[first]
            if value is not None and value == self.board[second] == self.board[third]:
                return value
        return None

    def get_status_text(self) -> str:
        """Return a short status message for the UI."""

        if self.winner is not None:
            return f"Winner: {self.winner}"
        if self.is_draw:
            return "Result: Draw"
        return f"Current turn: {self.current_player}"

    def is_game_over(self) -> bool:
        """Return True when the game has ended."""

        return self.winner is not None or self.is_draw

    def _is_valid_index(self, index: int) -> bool:
        """Return True for a board index inside the 3x3 grid."""

        return 0 <= index < 9
