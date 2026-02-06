"""Session logging for storing conversation history."""

import os
from datetime import datetime, timedelta
from pathlib import Path


class SessionLogger:
    """Log conversation sessions to files with auto-cleanup."""

    def __init__(self, sessions_dir: str = "data/sessions"):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._active_sessions: dict[str, str] = {}  # user_id -> filepath

    def log_incoming(
        self,
        user_id: str,
        user_name: str,
        message: str,
        is_voice: bool = False,
    ):
        """Log an incoming message immediately (before processing)."""
        timestamp = datetime.now()
        session_file = self._get_session_file(user_id, timestamp)
        time_str = timestamp.strftime("%H:%M")
        voice_marker = " [voice]" if is_voice else ""

        entry = f"\n## {time_str}\n\n*{user_name}*{voice_marker}: {message}\n"

        with open(session_file, "a") as f:
            f.write(entry)

    def log_response(self, user_id: str, response: str):
        """Log jarvis's response (appended after the incoming message)."""
        if user_id not in self._active_sessions:
            return
        session_file = Path(self._active_sessions[user_id])
        if not session_file.exists():
            return

        entry = f"\n*jarvis*: {response}\n"

        with open(session_file, "a") as f:
            f.write(entry)

    def log_message(
        self,
        user_id: str,
        user_name: str,
        message: str,
        response: str,
        is_voice: bool = False,
    ):
        """
        Log a message exchange to the session file.

        Creates a new session file if one doesn't exist for today.
        """
        timestamp = datetime.now()

        # Get or create session file for this user
        session_file = self._get_session_file(user_id, timestamp)

        # Format the entry
        time_str = timestamp.strftime("%H:%M")
        voice_marker = " [voice]" if is_voice else ""

        entry = f"""
## {time_str}

*{user_name}*{voice_marker}: {message}

*jarvis*: {response}
"""

        # Append to session file
        with open(session_file, "a") as f:
            f.write(entry)

    def log_error(self, user_id: str, user_name: str, message: str, error: str):
        """Log an error that occurred while processing a message."""
        timestamp = datetime.now()
        session_file = self._get_session_file(user_id, timestamp)
        time_str = timestamp.strftime("%H:%M")

        entry = f"""
## {time_str}

*{user_name}*: {message}

*jarvis* [ERROR]: {error}
"""
        with open(session_file, "a") as f:
            f.write(entry)

    def _get_session_file(self, user_id: str, timestamp: datetime) -> Path:
        """Get the current session file, creating if needed."""
        date_str = timestamp.strftime("%Y-%m-%d")

        # Check if we have an active session for today
        if user_id in self._active_sessions:
            existing = Path(self._active_sessions[user_id])
            if existing.exists() and existing.stem.startswith(date_str):
                return existing

        # Create new session file (will be renamed when session ends)
        time_str = timestamp.strftime("%H-%M")
        filename = f"{date_str}_{time_str}_ongoing.md"
        filepath = self.sessions_dir / filename

        # Initialize with header
        if not filepath.exists():
            filepath.write_text(f"# Session {date_str}\n")

        self._active_sessions[user_id] = str(filepath)
        return filepath

    def end_session(self, user_id: str):
        """
        Mark a session as ended by renaming the file with end time.
        """
        if user_id not in self._active_sessions:
            return

        filepath = Path(self._active_sessions[user_id])
        if not filepath.exists():
            return

        # Rename from ongoing to final with end time
        timestamp = datetime.now()
        end_time = timestamp.strftime("%H-%M")

        # Parse start time from filename
        stem = filepath.stem
        if "_ongoing" in stem:
            new_stem = stem.replace("_ongoing", f"_{end_time}")
            new_path = filepath.with_stem(new_stem)
            filepath.rename(new_path)

        del self._active_sessions[user_id]

    def cleanup_old_sessions(self, days: int = 3):
        """Remove session files older than specified days."""
        cutoff = datetime.now() - timedelta(days=days)

        for filepath in self.sessions_dir.glob("*.md"):
            try:
                # Parse date from filename (format: YYYY-MM-DD_...)
                date_str = filepath.stem[:10]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if file_date < cutoff:
                    filepath.unlink()
            except (ValueError, IndexError):
                # Skip files with unexpected format
                continue

    def get_recent_sessions(self, days: int = 3) -> list[dict]:
        """
        Get recent session summaries for context.

        Returns list of dicts with 'date', 'file', 'preview' keys.
        """
        cutoff = datetime.now() - timedelta(days=days)
        sessions = []

        for filepath in sorted(self.sessions_dir.glob("*.md"), reverse=True):
            try:
                date_str = filepath.stem[:10]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if file_date >= cutoff:
                    content = filepath.read_text()
                    sessions.append({
                        "date": date_str,
                        "file": filepath.name,
                        "path": str(filepath),
                        "preview": content[:500] if len(content) > 500 else content,
                        "full_content": content,
                    })
            except (ValueError, IndexError):
                continue

        return sessions

    def get_all_recent_content(self, days: int = 3) -> str:
        """Get all recent session content as a single string."""
        sessions = self.get_recent_sessions(days)
        if not sessions:
            return ""

        parts = []
        for session in sessions:
            parts.append(f"--- Session: {session['file']} ---\n{session['full_content']}")

        return "\n\n".join(parts)

    def get_last_n_messages(self, n: int = 20) -> list[dict]:
        """
        Get the last N messages across all sessions, most recent first.

        Returns list of dicts with 'timestamp', 'user', 'message', 'response' keys.
        """
        import re

        all_messages = []

        # Get all session files, sorted by name (which includes date)
        session_files = sorted(self.sessions_dir.glob("*.md"), reverse=True)

        # Pattern to match message blocks
        pattern = re.compile(
            r"## (\d{2}:\d{2})\n\n"
            r"\*(\w+)\*(?:\s*\[voice\])?: (.*?)\n\n"
            r"\*jarvis\*: (.*?)(?=\n\n## |\Z)",
            re.DOTALL
        )

        for filepath in session_files:
            if len(all_messages) >= n:
                break

            try:
                date_str = filepath.stem[:10]
                content = filepath.read_text()

                matches = list(pattern.finditer(content))
                # Reverse to get most recent first within this file
                for match in reversed(matches):
                    if len(all_messages) >= n:
                        break

                    time_str = match.group(1)
                    user = match.group(2)
                    message = match.group(3).strip()
                    response = match.group(4).strip()

                    all_messages.append({
                        "timestamp": f"{date_str} {time_str}",
                        "user": user,
                        "message": message,
                        "response": response,
                    })
            except (ValueError, IndexError):
                continue

        return all_messages

    def format_last_n_messages(self, n: int = 20) -> str:
        """Get last N messages formatted as readable text."""
        messages = self.get_last_n_messages(n)
        if not messages:
            return "No chat history found."

        parts = []
        for msg in messages:
            parts.append(
                f"[{msg['timestamp']}]\n"
                f"{msg['user']}: {msg['message']}\n"
                f"jarvis: {msg['response']}"
            )

        return "\n\n---\n\n".join(parts)
