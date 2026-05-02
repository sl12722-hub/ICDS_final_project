# ICDS Final Project

This project now uses one shared JSON message protocol for all socket
communication between the server and clients.

## Project Structure

- `server/protocol.py`: shared message format and helper functions
- `server/server.py`: threaded chat server
- `client/client.py`: terminal chat client
- `client/gui_client.py`: Tkinter GUI chat client

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
