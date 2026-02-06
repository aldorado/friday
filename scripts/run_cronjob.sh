#!/usr/bin/env bash
# Wrapper script for running Jarvis cronjobs
# Sets up the environment before running scheduled_task.py

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Preserve HOME before sourcing .env (cron provides minimal env)
SAVED_HOME="$HOME"

# Load .env if it exists
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Restore HOME if it was unset by .env
HOME="${HOME:-$SAVED_HOME}"

# Find uv in common locations (allow override via UV_PATH)
if [[ -z "$UV_PATH" ]]; then
    for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /usr/local/bin/uv /usr/bin/uv; do
        if [[ -x "$candidate" ]]; then
            UV_PATH="$candidate"
            break
        fi
    done
fi

if [[ -z "$UV_PATH" || ! -x "$UV_PATH" ]]; then
    echo "Error: uv not found. Install it or set UV_PATH." >&2
    exit 1
fi

# Find claude in common locations (allow override via CLAUDE_PATH)
if [[ -z "$CLAUDE_PATH" ]]; then
    for candidate in "$HOME/.local/bin/claude" "$HOME/.claude/local/claude" /usr/local/bin/claude /usr/bin/claude; do
        if [[ -x "$candidate" ]]; then
            CLAUDE_PATH="$candidate"
            break
        fi
    done
fi

if [[ -z "$CLAUDE_PATH" || ! -x "$CLAUDE_PATH" ]]; then
    echo "Error: claude not found. Install it or set CLAUDE_PATH." >&2
    exit 1
fi

# Run scheduled_task.py with the found paths
cd "$PROJECT_ROOT"
exec "$UV_PATH" run python "$SCRIPT_DIR/scheduled_task.py" "$@" --claude-path "$CLAUDE_PATH"
