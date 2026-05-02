"""Minimal Tic-Tac-Toe data model placeholder.

Issue #2 only organizes files. The game logic here is deliberately
lightweight so later issues can extend it safely.
"""

from __future__ import annotations


class TicTacToe:
    """Small placeholder board model for future game features."""

    def __init__(self) -> None:
        self.board = [" "] * 9
        self.current_player = "X"

    def snapshot(self) -> dict[str, object]:
        """Return the current board state in a simple dictionary."""

        return {"board": self.board[:], "current_player": self.current_player}
