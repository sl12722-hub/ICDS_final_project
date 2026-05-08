"""Server-side game room management for multiplayer Tic-Tac-Toe."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass

from game.tic_tac_toe import TicTacToe


@dataclass
class GameRoom:
    """Store the state of one game room."""

    room_id: str
    creator_name: str
    creator_socket: object
    x_player_name: str
    x_socket: object
    o_player_name: str | None = None
    o_socket: object | None = None
    game: TicTacToe | None = None

    def is_full(self) -> bool:
        """Return True when both players have joined."""

        return self.o_socket is not None

    def get_status(self) -> str:
        """Return a readable room status."""

        if self.is_full():
            return f"Room {self.room_id}: {self.x_player_name}(X) vs {self.o_player_name}(O)"
        return f"Room {self.room_id}: {self.x_player_name}(X) waiting for opponent"


class GameManager:
    """Create and manage Tic-Tac-Toe game rooms."""

    def __init__(self) -> None:
        self.rooms: dict[str, GameRoom] = {}
        self.player_in_game: dict[str, str] = {}  # {player_name: room_id}
        self.lock = threading.Lock()

    def create_room(self, creator_name: str, creator_socket: object) -> str:
        """Create a new game room and return the room ID."""

        with self.lock:
            if creator_name in self.player_in_game:
                return ""

            room_id = str(uuid.uuid4())[:8]
            room = GameRoom(
                room_id=room_id,
                creator_name=creator_name,
                creator_socket=creator_socket,
                x_player_name=creator_name,
                x_socket=creator_socket,
            )
            self.rooms[room_id] = room
            self.player_in_game[creator_name] = room_id
            return room_id

    def join_room(self, room_id: str, player_name: str, player_socket: object) -> tuple[bool, str]:
        """Join an existing room as the O player."""

        with self.lock:
            if player_name in self.player_in_game:
                return False, "You are already in a game."

            if room_id not in self.rooms:
                return False, f"Room {room_id} not found."

            room = self.rooms[room_id]
            if room.is_full():
                return False, "Room is full."

            room.o_player_name = player_name
            room.o_socket = player_socket
            self.player_in_game[player_name] = room_id
            
            # Initialize the game when both players have joined
            if room.game is None:
                room.game = TicTacToe()
            
            return True, room_id

    def get_room(self, room_id: str) -> GameRoom | None:
        """Return a room by ID, or None if not found."""

        with self.lock:
            return self.rooms.get(room_id)

    def list_open_rooms(self) -> list[str]:
        """Return the IDs of rooms not yet full."""

        with self.lock:
            return [room.room_id for room in self.rooms.values() if not room.is_full()]

    def remove_player(self, player_name: str) -> None:
        """Clean up when a player disconnects."""

        with self.lock:
            room_id = self.player_in_game.pop(player_name, None)
            if room_id and room_id in self.rooms:
                self.rooms.pop(room_id, None)

    def handle_move(self, room_id: str, player_name: str, row: int, col: int) -> tuple[bool, dict]:
        """Handle a player's move and return the game state."""

        with self.lock:
            if room_id not in self.rooms:
                return False, {"error": "Room not found"}

            room = self.rooms[room_id]
            if not room.game:
                return False, {"error": "Game not started"}

            # Determine player symbol
            if player_name == room.x_player_name:
                expected_player = "X"
            elif player_name == room.o_player_name:
                expected_player = "O"
            else:
                return False, {"error": "Player not in this room"}

            # Check if it's this player's turn
            if room.game.current_player != expected_player:
                return False, {"error": f"It is {room.game.current_player}'s turn"}

            # Validate and make the move
            if not room.game.make_move(row, col):
                return False, {"error": "Invalid move (cell occupied or out of bounds)"}

            # Return the updated game state
            game_state = {
                "board": room.game.board[:],  # Copy of board
                "current_player": room.game.current_player,
                "winner": room.game.winner,
                "is_draw": room.game.is_draw,
                "is_game_over": room.game.is_game_over(),
            }
            return True, game_state
