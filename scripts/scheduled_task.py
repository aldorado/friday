#!/usr/bin/env python3
"""Generic scheduled task runner for Jarvis cronjobs."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Load .env before any imports that need env vars
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jarvis.cron import CronManager


async def run_claude_task(task_name: str, task_description: str, claude_path: str) -> str:
    """Run a task through Claude Code."""
    prompt = f"""Scheduled task: {task_name}

{task_description}

CRITICAL RULES FOR SCHEDULED TASKS:
- Your ENTIRE output will be sent directly to the user via messaging platform as-is
- ONLY output the final message for the user - nothing else
- Do the "before responding" checklist (chat-history, memories, news.md) for context, but NEVER mention or output anything about those steps
- Do NOT output any internal thinking, planning, status updates, or meta-commentary
- Do NOT say things like "let me check..." or "now I'll send..." or "no news entries to process"
- Just do whatever work you need silently using tools, then output ONLY the final message
- Stay in character as jarvis"""

    project_root = Path(__file__).parent.parent

    # Disallowed tools (same as main runner - block dangerous operations)
    disallowed_tools = [
        "Read(*.env*)",
        "Read(**/.env*)",
        "Bash(cat *.env*)",
        "Bash(cat **/.env*)",
        "Bash(rm -rf*)",
        "Bash(rm -r /*)",
    ]

    args = [
        claude_path,
        "-p", prompt,
        "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        "--disallowedTools", *disallowed_tools,
    ]

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(project_root),
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        return f"Task failed: {stderr.decode()}"

    return stdout.decode()


def write_to_news(task_name: str, result: str) -> bool:
    """Write task result to news.md for the next conversation to pick up."""
    from datetime import datetime

    news_file = Path(__file__).parent.parent / "news.md"

    if not news_file.exists():
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Format the news entry
    entry = f"""
### {timestamp}
**task:** {task_name}
{result}

"""

    # Append to news.md
    with open(news_file, "a") as f:
        f.write(entry)

    return True


async def send_notification(task_name: str, result: str) -> bool:
    """Send task result via messaging platform. Returns True if sent successfully."""
    user_phone = os.environ.get("USER_PHONE_NUMBER")
    if not user_phone:
        return False

    try:
        from jarvis.platform import get_client
        from jarvis.message_store import MessageStore
        from jarvis.session_logger import SessionLogger

        project_root = Path(__file__).parent.parent
        client = get_client()
        message_store = MessageStore(project_root / "data")
        session_logger = SessionLogger(project_root / "data" / "sessions")

        # Truncate if too long (safe for both platforms)
        max_len = 3500
        if len(result) > max_len:
            result = result[:max_len] + "\n\n... (truncated)"

        message = result
        send_result = await client.send_text(user_phone, message)
        await client.close()

        # Store message for reply context lookups
        if msg_id := send_result.get("messages", [{}])[0].get("id"):
            message_store.store(msg_id, message, "jarvis")

        # Log to session history so it shows up in chat-history lookups
        session_logger.log_message(
            user_id=user_phone,
            user_name="scheduled",
            message=f"[scheduled task: {task_name}]",
            response=message,
        )

        return True
    except Exception as e:
        print(f"Notification failed: {e}", file=sys.stderr)
        return False


async def main_async(args):
    """Async main function."""
    # Run the task
    result = await run_claude_task(args.name, args.description, args.claude_path)

    wrote_news = False
    sent = False

    # Only notify if not silent
    if not args.silent:
        # Write to news.md for async pickup by next conversation
        wrote_news = write_to_news(args.name, result)

        # Also send via messaging platform for immediate notification
        sent = await send_notification(args.name, result)

    # Always print to stdout (for logging)
    print(f"Task '{args.name}' completed:")
    print(result)
    if wrote_news:
        print("(Written to news.md)")
    if sent:
        print("(Sent notification)")

    # Remove if one-shot
    if args.one_shot:
        cron = CronManager()
        cron.remove_task(args.name)
        print(f"One-shot task '{args.name}' removed from crontab")


def main():
    parser = argparse.ArgumentParser(description="Run a Jarvis scheduled task")
    parser.add_argument("name", help="Task name")
    parser.add_argument("description", help="Task description")
    parser.add_argument("--one-shot", action="store_true", help="Remove task after running")
    parser.add_argument("--silent", action="store_true", help="Don't send notifications (news.md or messaging platform)")
    parser.add_argument("--claude-path", required=True, help="Path to claude CLI")
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
