# ICDS Final Project

## Team Members

- `Sitong Li` - Led overall project architecture and backend integration, including the threaded server structure, shared JSON message protocol, chat history flow, AI configuration support, and final README/setup organization.
- `Yunzhi Li` - Led client-facing feature development, including the Tkinter GUI client, chatbot interaction and personality controls, multiplayer Tic-Tac-Toe integration, and end-to-end feature wiring and refinement.
- `Runzhang Zhu` - Contributed supporting feature modules and quality improvements, including summary and keyword extraction, sentiment-related functionality, error-handling polish, and test support for project stability.

## Project Overview

This project is a Python socket-based group chat system with a Tkinter GUI client and a threaded server. The system supports real-time messaging between multiple users, chatbot interaction, a multiplayer Tic-Tac-Toe game, and several bonus features such as chat summary, keyword extraction, sentiment display, and optional AI picture generation.

The project uses one shared JSON message protocol for all communication between the server and clients. This keeps the code organized and makes it easier to extend new features without changing the basic socket structure.

## Main Features

- GUI chat client with username login, online user list, message area, and send box
- Multi-user chat through one threaded server
- Chatbot support with per-user memory and personality switching
- Group chatbot interaction through `@bot`
- Multiplayer Tic-Tac-Toe with room creation and room joining
- Chat summary with `/summary`
- Keyword extraction with `/keywords`
- Sentiment labels shown beside chat messages
- Optional AI picture generation with `/aipic: ...`
- Friendly GUI error messages and readable server logs for demo use

## Required Packages

This project mainly uses the Python standard library. The extra packages below are needed for optional AI features.

- Python `3.10+` recommended
- `requests`
- `Pillow` for AI image preview
- `tkinter` for the GUI

Install the non-standard packages with:

```bash
python3 -m pip install requests pillow
```

Notes:

- `tkinter` is included with many Python installations, but some environments may require a Python build that includes Tk support.
- If you only want normal chat, summary, keywords, and game features, you do not need AI credentials.

## How to Run

### 1. Enter the project folder

```bash
cd "/Users/sitongli/Desktop/ICDS final project"
```

### 2. Optional: configure AI environment variables

These are only needed for chatbot replies and AI picture generation.

```bash
export OPENAI_API_KEY="your_key_here"
export OPENAI_BASE_URL="https://your-openai-compatible-endpoint"
export OPENAI_MODEL="your-model-name"
```

Notes:

- `OPENAI_API_KEY` is required only when you actually use the chatbot or AI picture feature.
- Normal chat, game, summary, keywords, and sentiment can run without these environment variables.

### 3. Start the server

Open a Terminal window and run:

```bash
python3 -m server.server
```

If the server starts correctly, the terminal should show a log like:

```text
Server listening on 0.0.0.0:12345
```

### 4. Start GUI clients

Open a second Terminal window:

```bash
cd "/Users/sitongli/Desktop/ICDS final project"
python3 -m client.gui_client
```

Open a third Terminal window for another user:

```bash
cd "/Users/sitongli/Desktop/ICDS final project"
python3 -m client.gui_client
```

In each GUI window:

1. Set `Host` to `127.0.0.1`
2. Set `Port` to `12345`
3. Enter a different username, such as `Alice` and `Bob`
4. Click `Connect`

After connecting, the message box becomes editable and you can start chatting.

### 5. Optional terminal client

There is also a terminal client in [client.py](/Users/sitongli/Desktop/ICDS final project/client/client.py), but the GUI client is the main interface used for the final project features and demo.

## Commands

Use these commands in the GUI message input box unless noted otherwise.

### Chatbot

Main supported command:

```text
@bot explain recursion simply
```

The chatbot also keeps short recent memory for each user, so prompts like these can work:

```text
@bot my name is Alice
@bot what is my name?
```

Personality command:

```text
/personality friendly
/personality funny
/personality serious
```

Important note:

- The current project uses `@bot` as the working chatbot trigger.
- `/bot:` appeared in earlier planning text, but it is not the main implemented GUI command now.

### Summary and Keywords

```text
/summary
/keywords
```

- `/summary` returns a short summary based on recent public chat history.
- `/keywords` returns the most frequent informative keywords from recent public chat history.
- These responses are sent privately to the requesting client.

### AI Picture Generation

```text
/aipic: a white cat sitting in a classroom drawing on the blackboard
```

- This feature is optional.
- It requires working AI configuration and internet access.
- Generated images are saved in the `generated_images/` folder.

### Game Usage

The Tic-Tac-Toe feature is currently controlled through GUI buttons, not slash commands.

1. One player clicks `Create Game`
2. The server returns a room ID
3. Another player enters that room ID in the `Room ID` box
4. The second player clicks `Join Game`
5. Both players receive a Tic-Tac-Toe window

Important note:

- `/game create` and `/game join` are not implemented as chat commands in the current version.
- Game creation and joining are done through the GUI controls.

## System Architecture

### High-level structure

```text
GUI Client / Terminal Client
          |
          v
   Shared JSON Protocol
          |
          v
      Chat Server
      /    |    \
 ChatHistory GameManager ChatbotManager
                    |
                    v
              ChatBotClient
```

### Main folders

```text
client/
  gui_client.py       Tkinter GUI client
  client.py           terminal client

server/
  server.py           main threaded chat server
  protocol.py         shared JSON message format
  chat_history.py     recent public chat storage
  game_manager.py     multiplayer game room logic

chatbot/
  chatbot_manager.py  command parsing, personality, memory
  chatbot_client.py   OpenAI-compatible chatbot API wrapper

game/
  tic_tac_toe.py      game rules
  game_window.py      Tkinter game window

bonus/
  sentiment.py        message sentiment labels
  summary_keywords.py offline summary and keyword extraction
  ai_picture.py       optional AI image generation

shared/
  ai_config.py        shared AI environment config helpers

tests/
  test_chatbot_client.py
  test_summary_keywords.py
  test_error_handling.py
```

### Component responsibilities

- `server/server.py` accepts clients, routes protocol messages, logs events, and coordinates all features.
- `client/gui_client.py` handles GUI login, chat display, commands, game actions, and user-friendly error messages.
- `server/protocol.py` defines the message format used everywhere.
- `server/chat_history.py` stores recent public chat messages for summary and keywords.
- `chatbot/chatbot_manager.py` handles `@bot` and `/personality`.
- `server/game_manager.py` manages Tic-Tac-Toe rooms, turns, and move validation.
- `bonus/summary_keywords.py` runs offline text analysis without extra APIs.

## Message Protocol

All socket communication uses newline-delimited JSON dictionaries with this shape:

```python
{
    "type": "chat",
    "sender": "Alice",
    "target": "all",
    "content": "Hello everyone",
    "timestamp": "2026-05-09 20:00:00",
    "extra": {}
}
```

### Standard fields

- `type`: message type
- `sender`: username or system component
- `target`: `all` or a specific user
- `content`: main text payload
- `timestamp`: message time
- `extra`: extra structured data for special features

### Supported message types

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

### Protocol helpers

Defined in [protocol.py](/Users/sitongli/Desktop/ICDS final project/server/protocol.py):

- `create_message(...)`
- `encode_message(...)`
- `decode_message(...)`

## Feature Demo Guide

This order works well for a class demo.

### 1. Normal chat

1. Start the server
2. Open two GUI clients
3. Connect as two different users
4. Send a few messages between the two windows
5. Show that both the sender and receiver see updates in real time

### 2. Sentiment analysis

Send messages such as:

```text
I am very happy today!
I am stressed about the deadline.
```

Show that the GUI adds sentiment labels to chat messages.

### 3. Keywords

Send a few topic-related messages, then type:

```text
/keywords
```

Show that the requesting client receives a private `Keywords: ...` response.

### 4. Summary

After more chat messages, type:

```text
/summary
```

Show that the requesting client receives a private `Summary: ...` response.

### 5. Chatbot

If AI credentials are configured, type:

```text
@bot explain recursion simply
```

Then test short memory:

```text
@bot my name is Alice
@bot what is my name?
```

Then change personality:

```text
/personality funny
```

### 6. Multiplayer Tic-Tac-Toe

1. Player A clicks `Create Game`
2. Show the generated room ID
3. Player B enters the room ID and clicks `Join Game`
4. Play a few moves and show board synchronization

### 7. Optional AI picture

If AI configuration is available, type:

```text
/aipic: a futuristic campus poster with students and robots
```

Show the saved image path and preview window.

## Known Limitations

- Chatbot and AI picture generation depend on working external AI configuration and internet access.
- The terminal client does not expose all GUI-only project features.
- Tic-Tac-Toe is launched through GUI buttons rather than chat commands.
- Chat summary and keywords are based only on recent public chat history, not the full session forever.
- Sentiment analysis is lightweight and may not always match human judgment.
- AI image quality depends on the external model and image service response.
- Team member names and final contribution details still need to be filled in before submission.

## Member Contributions

Replace this placeholder section with your final team breakdown.

- `[Member 1 Name]`: server architecture, protocol, integration
- `[Member 2 Name]`: GUI client, usability, demo preparation
- `[Member 3 Name]`: chatbot, AI integration
- `[Member 4 Name]`: game logic, testing, documentation

## Quick Start Checklist

For a grader or TA who wants the shortest path:

1. Install `requests` and `pillow`
2. Run `python3 -m server.server`
3. Run `python3 -m client.gui_client` in two more terminals
4. Connect both GUI clients to `127.0.0.1:12345`
5. Test normal chat, `/summary`, `/keywords`, and the game buttons
6. If AI credentials are available, test `@bot` and `/aipic: ...`
