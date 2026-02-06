#!/usr/bin/env bash
# Wrapper script for running proactive check-in
# Sets up the environment before running proactive_checkin.py

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Preserve HOME before sourcing .env
SAVED_HOME="$HOME"

# Load .env if it exists
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Restore HOME if it was unset
HOME="${HOME:-$SAVED_HOME}"

# Find uv
if [[ -z "$UV_PATH" ]]; then
    for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /usr/local/bin/uv /usr/bin/uv; do
        if [[ -x "$candidate" ]]; then
            UV_PATH="$candidate"
            break
        fi
    done
fi

if [[ -z "$UV_PATH" || ! -x "$UV_PATH" ]]; then
    echo "Error: uv not found" >&2
    exit 1
fi

# Random delay (0-45 min) to avoid running at exact hour marks
# This is done here because cron uses /bin/sh (dash) which doesn't support $RANDOM
DELAY=$((RANDOM % 2700))
echo "Sleeping ${DELAY}s before proactive check-in..."
sleep "$DELAY"

# Run proactive_checkin.py
cd "$PROJECT_ROOT"
exec "$UV_PATH" run python "$SCRIPT_DIR/proactive_checkin.py"
