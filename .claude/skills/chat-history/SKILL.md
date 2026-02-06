---
name: chat-history
description: Internal skill to retrieve recent chat history. Use when you need context from previous conversations - when the user references something you discussed before, or when "last time" or "earlier" is mentioned.
user-invocable: false
---

# Chat History Retrieval

Retrieve recent messages from our chat history across all sessions.

## Usage

Run this Python snippet to get the last N messages:

```bash
uv run python -c "
from jarvis.session_logger import SessionLogger
from pathlib import Path
logger = SessionLogger(str(Path('data/sessions').resolve()))
print(logger.format_last_n_messages(n=20))
"
```

Change `n=20` to get more or fewer messages.

## When to Use

- User says "remember when we talked about X" but you don't have it in context
- User references "last time" or "earlier today" or "yesterday"
- User asks "what did I say about X"
- You need to check what was discussed recently

## Output Format

Returns messages in reverse chronological order (most recent first):

```
[2026-01-31 00:57]
user: Hey you there
jarvis: hey, what's up?

---

[2026-01-30 22:15]
user: ...
jarvis: ...
```

## Notes

- All sessions are stored permanently in data/sessions/
- Messages include timestamps for context
- Search through the output for relevant keywords
