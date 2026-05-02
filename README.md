# ICDS Final Project

This project now uses one shared JSON message protocol for all socket
communication between the server and clients.

## Project Structure

```text
project/
  server/
    server.py
    protocol.py
    chat_history.py
    game_manager.py

  client/
    client.py
    gui_client.py

  chatbot/
    chatbot_client.py
    chatbot_manager.py

  game/
    tic_tac_toe.py
    game_window.py

  bonus/
    sentiment.py
    summary_keywords.py
    ai_picture.py

  docs/
    pi_mono_usage.md
    demo_script.md

  README.md
```

Current feature status:

- `server/` and `client/` contain working chat code.
- `chatbot/`, `game/`, and `bonus/` contain safe placeholder modules for future issues.
- No file uses a standard-library-conflicting name such as `json.py`, `socket.py`, `sys.py`, or `tkinter.py`.

## Unified Message Format

Every message sent over the socket follows this dictionary shape:

```python
{
    "type": "chat",
    "sender": "Ryan",
    "target": "all",
    "content": "Hello everyone",
    "timestamp": "2026-05-02 20:00:00",
    "extra": {}
}
```

Messages are sent as newline-delimited JSON. This keeps the socket logic
simple because the server and clients can read one full message at a time.

## Supported Message Types

- `chat`
- `system`
- `bot_request`
- `bot_response`
- `game_create`
- `game_join`
- `game_start`
- `game_move`
- `game_state`
- `game_end`
- `summary_request`
- `summary_response`
- `keywords_request`
- `keywords_response`
- `sentiment_result`
- `error`

## Protocol Helper Functions

`server/protocol.py` provides:

- `create_message(msg_type, sender, content, target="all", extra=None)`
- `encode_message(message)`
- `decode_message(raw_data)`

## How To Run

Open a terminal in the project folder and start the server:

```bash
python -m server.server
```

Open a second terminal for the first client:

```bash
python -m client.client --username Ryan
```

Open a third terminal for the second client:

```bash
python -m client.client --username Alex
```

You can also start the GUI client instead of the terminal client:

```bash
python -m client.gui_client
```

## Import Safety

- Each feature folder is a Python package with an `__init__.py` file.
- Shared socket message helpers stay in `server/protocol.py`.
- New folders were added without renaming `server/server.py` or `client/client.py`, so existing run commands still work.

## How To Test Normal Chat With Two Clients

1. Run `python -m server.server`.
2. Run `python -m client.client --username Ryan`.
3. Run `python -m client.client --username Alex`.
4. Type `Hello` in Ryan's client and press Enter.
5. Check that both clients display the same chat message.
6. Type `/quit` in one client and confirm the other client sees the disconnect system message.

## Safety Checks

- Invalid JSON data is caught and returns an `error` message instead of crashing the server.
- Missing required fields are caught by protocol validation.
- Unknown message types return an `error` message.
- The server ignores client-created `error` messages and blocks client-created `system` messages.
- Placeholder modules were added for future chatbot, game, and bonus features without changing current chat behavior.
