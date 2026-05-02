"""Server-side placeholders for multiplayer game sessions."""

from __future__ import annotations


class GameManager:
    """Track whether a game feature has been added yet."""

    def __init__(self) -> None:
        self.active_games: dict[str, dict[str, object]] = {}

    def list_games(self) -> list[str]:
        """Return current game IDs for future integrations."""

        return list(self.active_games.keys())
