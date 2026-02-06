"""Claude Code CLI wrapper for running conversations."""

import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from .memory import MemoryManager
from .session_logger import SessionLogger

SESSION_TIMEOUT = 30 * 60  # 30 minutes


def find_claude_cli() -> Optional[str]:
    """Find claude CLI in common locations."""
    home = os.environ.get("HOME", os.path.expanduser("~"))
    candidates = [
        os.path.join(home, ".local", "bin", "claude"),
        os.path.join(home, ".claude", "local", "claude"),
        "/usr/local/bin/claude",
        "/usr/bin/claude",
    ]
    # Also check CLAUDE_PATH env var
    if env_path := os.environ.get("CLAUDE_PATH"):
        candidates.insert(0, env_path)

    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


@dataclass
class ClaudeResponse:
    """Structured response from Claude."""

    response_text: str
    send_voice: bool
    voice_text: Optional[str]
    conversation_finished: bool
    memories_to_save: list[str]
    code_changes: bool
    raw_output: str
    session_id: Optional[str]


# JSON schema for Claude's structured output
RESPONSE_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "response_text": {
            "type": "string",
            "description": "The text response to send to the user",
        },
        "send_voice": {
            "type": "boolean",
            "description": "Whether to send a voice message instead of/in addition to text",
        },
        "voice_text": {
            "type": "string",
            "description": "Text with [emotion] tags for ElevenLabs TTS (e.g., '[excited] oh that's cool!')",
        },
        "conversation_finished": {
            "type": "boolean",
            "description": "Whether this topic/conversation is wrapped up",
        },
        "memories_to_save": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Important points to save to memory (preferences, decisions, project updates)",
        },
        "code_changes": {
            "type": "boolean",
            "description": "Set to true if you made code changes to jarvis that require a restart",
        },
    },
    "required": ["response_text", "send_voice", "conversation_finished"],
})


class ClaudeRunner:
    """Run Claude Code CLI with structured output."""

    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).absolute()
        self.memory = MemoryManager(self.project_dir / "data")
        self.session_logger = SessionLogger(self.project_dir / "data" / "sessions")
        self.sessions_file = self.project_dir / "data" / "sessions.json"
        self.sessions_file.parent.mkdir(exist_ok=True)

    def _load_sessions(self) -> dict:
        """Load session tracking data."""
        if self.sessions_file.exists():
            return json.loads(self.sessions_file.read_text())
        return {}

    def _save_sessions(self, sessions: dict):
        """Save session tracking data."""
        self.sessions_file.write_text(json.dumps(sessions, indent=2))

    def get_session_id(self, user_id: str) -> Optional[str]:
        """Get existing session ID for a user if not expired."""
        sessions = self._load_sessions()
        session_data = sessions.get(user_id, {})

        session_id = session_data.get("session_id")
        last_activity = session_data.get("last_activity", 0)

        if not session_id:
            return None

        # Check if session has timed out (30 min)
        if time.time() - last_activity > SESSION_TIMEOUT:
            # Session expired, clear it
            sessions.pop(user_id, None)
            self._save_sessions(sessions)
            return None

        return session_id

    def update_session(self, user_id: str, session_id: str, finished: bool = False):
        """Update session tracking for a user."""
        sessions = self._load_sessions()
        if finished:
            # Clear session when conversation finishes
            sessions.pop(user_id, None)
        else:
            sessions[user_id] = {
                "session_id": session_id,
                "last_activity": time.time(),
            }
        self._save_sessions(sessions)

    async def run(
        self,
        message: str,
        user_id: str,
        user_name: Optional[str] = None,
        is_voice: bool = False,
        image_path: Optional[str] = None,
        quoted_message: Optional[str] = None,
    ) -> ClaudeResponse:
        """
        Run Claude Code with a user message.

        Args:
            message: The user's message
            user_id: Unique user identifier (phone number)
            user_name: User's display name
            is_voice: Whether the message was a voice message
            image_path: Path to image file if message includes an image
            quoted_message: Content of the message being replied to (if any)

        Returns:
            ClaudeResponse with structured output
        """
        # Get current Vienna time
        vienna_tz = ZoneInfo("Europe/Vienna")
        vienna_now = datetime.now(vienna_tz)
        vienna_time_str = vienna_now.strftime("%Y-%m-%d %H:%M (%A)")

        # Build the prompt
        prompt_parts = []
        prompt_parts.append("[Platform: WhatsApp]")
        if user_name:
            prompt_parts.append(f"[User: {user_name}]")
        prompt_parts.append(f"[Vienna time: {vienna_time_str}]")
        if is_voice:
            prompt_parts.append("[Voice message transcription]")
        if image_path:
            prompt_parts.append(f"[Image attached - use Read tool to view: {image_path}]")
        if quoted_message:
            prompt_parts.append(f"[Replying to: {quoted_message}]")
        prompt_parts.append(f"\nMessage: {message}")

        full_prompt = "\n".join(prompt_parts)

        # Find claude CLI
        claude_path = find_claude_cli()
        if not claude_path:
            return ClaudeResponse(
                response_text="sorry, claude cli not found on this system",
                send_voice=False,
                voice_text=None,
                conversation_finished=False,
                memories_to_save=[],
                raw_output="",
                session_id=None,
            )

        # Build CLI command
        cmd = [
            claude_path,
            "-p", full_prompt,
            "--output-format", "json",
            "--json-schema", RESPONSE_SCHEMA,
            "--permission-mode", "bypassPermissions",
            "--disallowedTools", "Read(*.env*)", "Read(**/.env*)", "Bash(cat *.env*)", "Bash(cat **/.env*)", "Bash(rm -rf*)", "Bash(rm -r /*)",
        ]

        # Check for existing session
        session_id = self.get_session_id(user_id)
        if session_id:
            cmd.extend(["--resume", session_id])

        # Run Claude Code
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.project_dir),
            env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            stdout_msg = stdout.decode() if stdout else ""
            import logging
            logging.getLogger("jarvis").error(f"Claude failed (code {process.returncode}): stderr={error_msg}, stdout={stdout_msg[:500]}")
            return ClaudeResponse(
                response_text=f"sorry, something went wrong... ({error_msg[:100]})",
                send_voice=False,
                voice_text=None,
                conversation_finished=False,
                memories_to_save=[],
                raw_output=error_msg,
                session_id=None,
            )

        # Parse output
        raw_output = stdout.decode()
        try:
            output = json.loads(raw_output)
        except json.JSONDecodeError:
            return ClaudeResponse(
                response_text=raw_output[:1000] if raw_output else "no response",
                send_voice=False,
                voice_text=None,
                conversation_finished=False,
                memories_to_save=[],
                raw_output=raw_output,
                session_id=None,
            )

        # Extract session ID from output if present
        new_session_id = output.get("session_id") or session_id

        # Handle result field - Claude uses structured_output for JSON schema responses
        result = output.get("structured_output") or output.get("result") or output
        if isinstance(result, str):
            if not result:  # empty string
                result = {"response_text": "hmm, i didn't have anything to say", "send_voice": False, "conversation_finished": False}
            else:
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {"response_text": result, "send_voice": False, "conversation_finished": False}

        response = ClaudeResponse(
            response_text=result.get("response_text", ""),
            send_voice=result.get("send_voice", False),
            voice_text=result.get("voice_text"),
            conversation_finished=result.get("conversation_finished", False),
            memories_to_save=result.get("memories_to_save", []),
            code_changes=result.get("code_changes", False),
            raw_output=raw_output,
            session_id=new_session_id,
        )

        # Update session tracking
        if new_session_id:
            self.update_session(user_id, new_session_id, response.conversation_finished)

        # Log response (incoming message was already logged before Claude ran)
        self.session_logger.log_response(
            user_id=user_id,
            response=response.response_text or response.voice_text or "",
        )

        # End session logging if conversation finished
        if response.conversation_finished:
            self.session_logger.end_session(user_id)

        # Keep all sessions permanently for chat history retrieval
        # (previously cleaned up after 3 days)

        # Save memories if any
        if response.memories_to_save:
            for memory in response.memories_to_save:
                self.memory.save(memory)

        return response
