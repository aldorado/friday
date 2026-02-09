"""Simple message store for tracking sent/received messages."""

import json
from datetime import datetime, timedelta
from pathlib import Path


class MessageStore:
    """Store messages keyed by message ID for reply context lookup."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.store_file = self.data_dir / "messages.json"

    def _load(self) -> dict:
        if self.store_file.exists():
            return json.loads(self.store_file.read_text())
        return {}

    def _save(self, data: dict):
        self.store_file.write_text(json.dumps(data, indent=2))

    def store(self, message_id: str, content: str, sender: str):
        """Store a message for later lookup."""
        data = self._load()
        data[message_id] = {
            "content": content,
            "sender": sender,
            "timestamp": datetime.now().isoformat(),
        }
        self._save(data)

    def get(self, message_id: str) -> dict | None:
        """Get a message by ID."""
        data = self._load()
        return data.get(message_id)

    def is_processed(self, message_id: str) -> bool:
        """Check if a message has already been processed (for dedup)."""
        data = self._load()
        return message_id in data

    def cleanup(self, days: int = 7):
        """Remove messages older than specified days."""
        cutoff = datetime.now() - timedelta(days=days)
        data = self._load()
        cleaned = {}
        for msg_id, msg in data.items():
            try:
                ts = datetime.fromisoformat(msg["timestamp"])
                if ts > cutoff:
                    cleaned[msg_id] = msg
            except (KeyError, ValueError):
                continue
        self._save(cleaned)
